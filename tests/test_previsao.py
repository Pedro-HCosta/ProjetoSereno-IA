"""Funcionalidade 1 — previsão de calma (modelo treinado em ml/modelo)."""
import pytest

from app import llm


def prever(cliente, cabecalho, **corpo):
    return cliente.post("/ia/previsao-calma", json={"localId": 1, "diaSemana": 1, "hora": 8} | corpo, headers=cabecalho)


def test_resposta_tem_o_formato_do_contrato(cliente, cabecalho):
    r = prever(cliente, cabecalho)
    assert r.status_code == 200
    d = r.json()
    assert 0 <= d["nivelPrevisto"] <= 100
    assert d["faixa"] in {"TRANQUILO", "MODERADO", "AGITADO"}
    assert d["explicacao"]


def test_sem_llm_usa_texto_alternativo_e_nao_quebra(cliente, cabecalho):
    d = prever(cliente, cabecalho).json()
    assert d["geradoPor"] == "regra"
    assert "UBS Vila Mariana" in d["explicacao"]


def test_com_llm_usa_a_frase_gerada(cliente, cabecalho, monkeypatch):
    recebido = {}

    def falso(sistema, usuario, **kw):
        recebido["dados"] = usuario
        return "Segunda às 8h deve estar cheio; prefira depois das 14h."

    monkeypatch.setattr(llm, "gerar", falso)
    d = prever(cliente, cabecalho).json()
    assert d["geradoPor"] == "llm"
    assert d["explicacao"].startswith("Segunda às 8h")
    assert "UBS Vila Mariana" in recebido["dados"]  # o LLM recebe só os dados calculados


def test_falha_do_llm_cai_no_texto_alternativo(cliente, cabecalho, monkeypatch):
    def quebra(*a, **kw):
        raise llm.LLMIndisponivel("timeout")

    monkeypatch.setattr(llm, "gerar", quebra)
    assert prever(cliente, cabecalho).json()["geradoPor"] == "regra"


def test_ubs_segunda_cedo_e_mais_cheia_que_a_tarde(cliente, cabecalho):
    cedo = prever(cliente, cabecalho, hora=8).json()["nivelPrevisto"]
    tarde = prever(cliente, cabecalho, hora=16).json()["nivelPrevisto"]
    assert cedo > tarde + 15


def test_melhor_horario_fica_dentro_do_funcionamento(cliente, cabecalho):
    d = prever(cliente, cabecalho, hora=8).json()
    assert 7 <= d["melhorHorario"] < 19
    assert d["melhorHorario"] != 8


def test_horario_fora_do_funcionamento_gera_alerta(cliente, cabecalho):
    d = prever(cliente, cabecalho, diaSemana=0, hora=10).json()  # UBS no domingo
    assert d["melhorHorario"] is None
    assert any("costumam estar fechados" in a for a in d["alertas"])


@pytest.mark.parametrize("dia,hora", [("SEGUNDA", "08:00"), ("segunda-feira", "8"), (1, 8)])
def test_aceita_dia_e_hora_em_formatos_diferentes(cliente, cabecalho, dia, hora):
    d = prever(cliente, cabecalho, diaSemana=dia, hora=hora)
    assert d.status_code == 200
    assert d.json()["nivelPrevisto"] == prever(cliente, cabecalho).json()["nivelPrevisto"]


def test_local_inexistente_responde_404(cliente, cabecalho):
    r = prever(cliente, cabecalho, localId=999)
    assert r.status_code == 404
    assert r.json()["erro"] == "NAO_ENCONTRADO"


def test_segunda_chamada_igual_vem_do_cache_sem_gastar_tokens(cliente, cabecalho, monkeypatch):
    chamadas = {"n": 0}

    def falso(*a, **kw):
        chamadas["n"] += 1
        return "Frase do LLM."

    monkeypatch.setattr(llm, "gerar", falso)
    primeira = prever(cliente, cabecalho).json()
    segunda = prever(cliente, cabecalho).json()
    assert primeira == segunda and chamadas["n"] == 1


def test_texto_alternativo_nao_vai_para_o_cache(cliente, cabecalho, monkeypatch):
    assert prever(cliente, cabecalho).json()["geradoPor"] == "regra"  # sem chave
    monkeypatch.setattr(llm, "gerar", lambda *a, **k: "Agora o LLM voltou.")
    assert prever(cliente, cabecalho).json()["geradoPor"] == "llm"


# --- Tipos de lugar da API Java (12 tipos) ---

class _RespostaJava:
    def __init__(self, status, corpo=None):
        self.status_code, self._corpo = status, corpo or {}

    def json(self):
        return self._corpo


def _java(monkeypatch, resposta):
    import httpx

    monkeypatch.setenv("JAVA_API_URL", "https://java.exemplo")
    chamadas = []

    def falso_get(url, **kw):
        chamadas.append(url)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta

    monkeypatch.setattr(httpx, "get", falso_get)
    return chamadas


@pytest.mark.parametrize("tipo", ["PARQUE", "BIBLIOTECA", "MUSEU", "CENTRO_CULTURAL", "SHOPPING",
                                  "RESTAURANTE", "CAFE", "TRANSPORTE", "SAUDE", "SERVICO_PUBLICO",
                                  "EDUCACAO", "OUTRO", "tipo-que-nao-existe"])
def test_todos_os_tipos_do_java_tem_previsao(cliente, cabecalho, monkeypatch, tipo):
    _java(monkeypatch, _RespostaJava(200, {"nome": "Lugar do Java", "categoria": tipo}))
    r = prever(cliente, cabecalho, localId=50, diaSemana=3, hora=15)
    assert r.status_code == 200, r.json()
    assert 0 <= r.json()["nivelPrevisto"] <= 100


def test_museu_fechado_na_segunda_usa_o_horario_do_tipo(cliente, cabecalho, monkeypatch):
    _java(monkeypatch, _RespostaJava(200, {"nome": "MASP", "categoria": "MUSEU"}))
    d = prever(cliente, cabecalho, localId=50, diaSemana=1, hora=15).json()
    assert d["melhorHorario"] is None
    assert any("museu" in a for a in d["alertas"])


def test_lugar_do_java_fica_em_cache(cliente, cabecalho, monkeypatch):
    chamadas = _java(monkeypatch, _RespostaJava(200, {"nome": "Parque", "categoria": "PARQUE"}))
    prever(cliente, cabecalho, localId=50, hora=9)
    prever(cliente, cabecalho, localId=50, hora=10)
    assert len(chamadas) == 1


def test_java_fora_do_ar_com_lugar_desconhecido_responde_503(cliente, cabecalho, monkeypatch):
    import httpx

    _java(monkeypatch, httpx.ConnectTimeout("Render dormindo"))
    assert prever(cliente, cabecalho, localId=50).status_code == 503
    assert prever(cliente, cabecalho, localId=1).status_code == 200  # cai no catálogo local


def test_java_404_responde_404(cliente, cabecalho, monkeypatch):
    _java(monkeypatch, _RespostaJava(404))
    assert prever(cliente, cabecalho, localId=50).status_code == 404
