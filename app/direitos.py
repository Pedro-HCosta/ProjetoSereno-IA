"""Funcionalidade 2 — "Quais são meus direitos?" (RAG sobre 3 leis + resposta do LLM citando artigos)."""
import re
from functools import lru_cache
from pathlib import Path

from . import cache, llm
from .config import carregar
from .erros import ErroApi
from .rag_motor import LEIS, Buscador

K = 3
# Abaixo disso, o trecho mais parecido ainda é distante demais da pergunta: o serviço diz que não sabe.
# Calibrado com as perguntas de rag/avaliacao (ver rag/RESULTADOS.md).
LIMIAR_RELEVANCIA = 0.13

NOMES_LEIS = ", ".join(m["lei"] for m in LEIS.values())
RESPOSTA_SEM_BASE = (
    f"Não encontrei nas leis que consulto ({NOMES_LEIS}) uma base segura para responder isso. "
    "Se for uma situação de acessibilidade, tente descrevê-la com outras palavras. "
    "Para um caso concreto, procure a Defensoria Pública ou o Ministério Público."
)
SINAL_SEM_BASE = "NAO_SEI"

SISTEMA = (
    "Você orienta cidadãos brasileiros (pessoas com deficiência, mobilidade reduzida ou autismo) sobre "
    "seus direitos de acessibilidade. Responda SOMENTE com base nos trechos de lei fornecidos. "
    "Regras: (1) português do Brasil, linguagem simples, de 3 a 6 frases, sem juridiquês; "
    "(2) cite a lei e o artigo de cada afirmação EXATAMENTE no formato (Lei 13.146/2015, art. 48), "
    "usando só os artigos que aparecem no cabeçalho dos trechos, sem citar parágrafo, inciso ou alínea; "
    "(3) cada frase precisa estar dita no trecho citado: não acrescente documentos exigidos, prazos, valores, "
    "órgãos, equipamentos alternativos nem procedimentos que os trechos não mencionem; "
    "(4) se os trechos disserem o que a pessoa pode fazer, termine com isso; se não disserem, termine "
    "recomendando procurar o responsável pelo local ou a Defensoria Pública, sem inventar o passo a passo; "
    f"(5) se os trechos não respondem à pergunta, responda exatamente {SINAL_SEM_BASE} e nada mais."
)


@lru_cache(maxsize=1)
def _buscador(pasta: str) -> Buscador:
    return Buscador(Path(pasta))


def indice_carregado() -> bool:
    try:
        _buscador(str(carregar().caminho_indice))
        return True
    except (FileNotFoundError, RuntimeError, OSError):
        return False


def buscar(consulta: str, k: int = K):
    try:
        return _buscador(str(carregar().caminho_indice)).buscar(consulta, k)
    except (FileNotFoundError, RuntimeError, OSError):
        raise ErroApi(503, "SERVICO_INDISPONIVEL", "Base de leis não indexada. Rode python -m rag.indexar.")


def _fonte(trecho: dict, nota: float) -> dict:
    texto = re.sub(r"\s+", " ", trecho["texto"])
    return {
        "lei": trecho["lei"],
        "artigo": trecho["artigo"],
        "trecho": texto if len(texto) <= 450 else texto[:447].rsplit(" ", 1)[0] + "...",
        "url": trecho["url"],
        "relevancia": round(nota, 3),
    }


def responder(situacao: str, contexto: str | None) -> dict:
    consulta = f"{situacao}. {contexto}" if contexto else situacao
    k = cache.chave("direitos", consulta)
    guardado = cache.obter(k)
    if guardado:
        return guardado
    achados = buscar(consulta)

    if not achados or achados[0][1] < LIMIAR_RELEVANCIA:
        return {"resposta": RESPOSTA_SEM_BASE, "fontes": [], "encontrouBase": False, "geradoPor": "regra"}

    fontes = [_fonte(t, n) for t, n in achados]
    blocos = "\n\n".join(f"[{i}] {t['lei']}, {t['artigo']}:\n{t['texto']}" for i, (t, _) in enumerate(achados, 1))
    pergunta = f"Situação do cidadão: {situacao}\n"
    if contexto:
        pergunta += f"Contexto: {contexto}\n"
    pergunta += f"\nTrechos de lei encontrados:\n\n{blocos}"

    try:
        texto = llm.gerar(SISTEMA, pergunta, max_tokens=500, temperatura=0.1)
    except llm.LLMIndisponivel:
        refs = "; ".join(f"{f['lei']}, {f['artigo']}" for f in fontes)
        return {
            "resposta": "Não consegui gerar a explicação agora, mas estes são os artigos das leis mais "
                        f"relacionados à sua situação: {refs}. Toque em cada fonte para ler o texto.",
            "fontes": fontes,
            "encontrouBase": True,
            "geradoPor": "regra",
        }

    if SINAL_SEM_BASE in texto.upper().replace("Ã", "A"):
        resultado = {"resposta": RESPOSTA_SEM_BASE, "fontes": [], "encontrouBase": False, "geradoPor": "llm"}
    else:
        resultado = {"resposta": texto, "fontes": fontes, "encontrouBase": True, "geradoPor": "llm"}
    cache.guardar(k, resultado)
    return resultado
