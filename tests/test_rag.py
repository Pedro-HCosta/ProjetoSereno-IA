"""Funcionalidade 2 — RAG: leitura das leis, índice, recusa fora do tema e resposta do LLM."""
from pathlib import Path

import pytest

from app import direitos, llm
from app.rag_motor import Buscador, construir_indice, dividir_por_artigo, texto_da_lei

FIXTURE = Path(__file__).parent / "fixtures" / "lei_ficticia.htm"
META = {"lei": "Lei de Teste 1/2000", "url": "https://exemplo.gov.br/lei-teste"}


@pytest.fixture
def trechos():
    return dividir_por_artigo(texto_da_lei(FIXTURE), META)


def test_divide_por_artigo(trechos):
    assert [t["artigo"] for t in trechos] == ["art. 1º", "art. 2º", "art. 3º", "art. 5º-A"]


def test_remove_texto_revogado_e_notas(trechos):
    tudo = " ".join(t["texto"] for t in trechos)
    assert "dez anos" not in tudo  # texto riscado = revogado
    assert "Artigo revogado" not in tudo
    assert "Redação dada" not in tudo and "Incluído pela" not in tudo
    assert "cinco anos" in tudo


def test_titulos_viram_contexto_e_nao_texto(trechos):
    art2, art3 = trechos[1], trechos[2]
    assert "DO ATENDIMENTO PRIORITÁRIO" not in art2["texto"]  # nome do capítulo seguinte
    assert art3["capitulo"].startswith("CAPÍTULO II — DO ATENDIMENTO PRIORITÁRIO")
    assert "Seção I — Disposições Gerais" in art3["capitulo"]


def test_corta_a_assinatura(trechos):
    assert "Brasília" not in trechos[-1]["texto"] and "FULANO" not in trechos[-1]["texto"]


def test_busca_encontra_o_artigo_certo(trechos, tmp_path):
    construir_indice(trechos, tmp_path)
    b = Buscador(tmp_path)
    assert b.buscar("o elevador da estação está parado", 1)[0][0]["artigo"] == "art. 1º"
    assert "art. 3º" in [t["artigo"] for t, _ in b.buscar("tenho prioridade na fila?", 2)]


# ---- endpoint (usa o índice de teste)

@pytest.fixture
def indice_teste(trechos, tmp_path, monkeypatch):
    construir_indice(trechos, tmp_path)
    monkeypatch.setenv("INDICE_PATH", str(tmp_path))
    direitos._buscador.cache_clear()
    yield
    direitos._buscador.cache_clear()


def perguntar(cliente, cabecalho, situacao="O elevador da estação está parado. Quais são meus direitos?", contexto="Estação Sé"):
    return cliente.post("/ia/direitos", json={"situacao": situacao, "contexto": contexto}, headers=cabecalho)


def test_sem_token_responde_401(cliente, indice_teste):
    assert cliente.post("/ia/direitos", json={"situacao": "elevador parado"}).status_code == 401


def test_sem_llm_devolve_os_artigos_encontrados(cliente, cabecalho, indice_teste):
    d = perguntar(cliente, cabecalho).json()
    assert d["encontrouBase"] is True and d["geradoPor"] == "regra"
    assert d["fontes"][0]["artigo"] == "art. 1º"
    assert len(d["fontes"]) <= 3
    assert "não substitui" in d["aviso"]


def test_com_llm_responde_citando_os_trechos(cliente, cabecalho, indice_teste, monkeypatch):
    recebido = {}

    def falso(sistema, usuario, **kw):
        recebido["prompt"] = usuario
        return "A estação deve manter o elevador funcionando (Lei de Teste 1/2000, art. 1º)."

    monkeypatch.setattr(llm, "gerar", falso)
    d = perguntar(cliente, cabecalho).json()
    assert d["geradoPor"] == "llm" and "art. 1º" in d["resposta"]
    assert "Art. 1º" in recebido["prompt"]  # o LLM recebeu o texto do artigo


def test_llm_sem_base_vira_resposta_de_nao_sei(cliente, cabecalho, indice_teste, monkeypatch):
    monkeypatch.setattr(llm, "gerar", lambda *a, **k: "NAO_SEI")
    d = perguntar(cliente, cabecalho).json()
    assert d["encontrouBase"] is False and d["fontes"] == []


def test_pergunta_fora_do_tema_nao_chama_o_llm(cliente, cabecalho, indice_teste, monkeypatch):
    def nao_deveria(*a, **k):
        raise AssertionError("o LLM não deveria ser chamado")

    monkeypatch.setattr(llm, "gerar", nao_deveria)
    # O índice de teste tem só 3 dimensões, e a escala das notas é outra: usa um limiar próprio.
    # O limiar real (0,13) é testado com o índice das leis em test_fora_do_tema_com_indice_real.
    monkeypatch.setattr(direitos, "LIMIAR_RELEVANCIA", 0.20)
    d = perguntar(cliente, cabecalho, situacao="Qual é a receita de bolo de cenoura com cobertura?", contexto=None).json()
    assert d["encontrouBase"] is False


def test_indice_ausente_responde_503(cliente, cabecalho, tmp_path, monkeypatch):
    monkeypatch.setenv("INDICE_PATH", str(tmp_path / "nao-existe"))
    direitos._buscador.cache_clear()
    r = perguntar(cliente, cabecalho)
    assert r.status_code == 503 and r.json()["erro"] == "SERVICO_INDISPONIVEL"
    direitos._buscador.cache_clear()


def test_situacao_curta_demais_responde_400(cliente, cabecalho, indice_teste):
    r = cliente.post("/ia/direitos", json={"situacao": "oi"}, headers=cabecalho)
    assert r.status_code == 400 and r.json()["campos"][0]["campo"] == "situacao"


# ---- regressão com o índice REAL das 3 leis (pula se o índice ainda não foi gerado)

INDICE_REAL = Path(__file__).resolve().parent.parent / "rag" / "indice"


@pytest.mark.skipif(not (INDICE_REAL / "leis.faiss").exists(), reason="rode python -m rag.indexar")
@pytest.mark.parametrize("pergunta", [
    "O elevador da estação está parado e eu sou cadeirante. Estação Sé",
    "Sou cadeirante e a escada rolante do metrô não funciona",
    "Quais são meus direitos?. Estação Paulista · elevador parado",
    "A plataforma elevatória do trem quebrou",
])
def test_fluxo_principal_traz_o_direito_ao_transporte(pergunta):
    artigos = [(t["lei"], t["artigo"]) for t, _ in Buscador(INDICE_REAL).buscar(pergunta, 3)]
    assert ("Lei 13.146/2015", "art. 48") in artigos or ("Lei 13.146/2015", "art. 46") in artigos


@pytest.mark.skipif(not (INDICE_REAL / "leis.faiss").exists(), reason="rode python -m rag.indexar")
@pytest.mark.parametrize("pergunta", ["Qual é a capital da França?", "Como faço para trocar o pneu do carro?"])
def test_fora_do_tema_com_indice_real(cliente, cabecalho, monkeypatch, pergunta):
    monkeypatch.setenv("INDICE_PATH", str(INDICE_REAL))
    direitos._buscador.cache_clear()
    monkeypatch.setattr(llm, "gerar", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria chamar o LLM")))
    d = cliente.post("/ia/direitos", json={"situacao": pergunta}, headers=cabecalho).json()
    direitos._buscador.cache_clear()
    assert d["encontrouBase"] is False and d["fontes"] == []
