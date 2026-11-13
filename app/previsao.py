"""Funcionalidade 1 — previsão do horário calmo (Machine Learning + frase gerada por LLM)."""
import json
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from . import cache, llm
from .config import carregar
from .erros import ErroApi
from .features import ALVOS, faixa, matriz, nivel_sobrecarga, perfil
from .schemas import NOMES_DIAS

TEXTO_FAIXA = {"TRANQUILO": "tranquilo", "MODERADO": "com movimento moderado", "AGITADO": "agitado"}
LIMIAR_ALERTA = 3.5  # nota prevista (1–5) a partir da qual vale avisar

SISTEMA = (
    "Você escreve para pessoas com sensibilidade sensorial (autismo, TDAH, ansiedade) que estão "
    "planejando ir a um lugar. Escreva em português do Brasil, em no máximo 2 frases curtas, com "
    "linguagem simples e acolhedora, sem emojis e sem termos técnicos. Use apenas os dados recebidos: "
    "não cite níveis nem notas numéricas e não invente horários nem informações sobre o lugar. Se houver um horário mais tranquilo "
    "no mesmo dia, sugira-o. Não mencione modelos, previsões estatísticas nem inteligência artificial."
)


class ModeloIndisponivel(Exception):
    pass


@lru_cache(maxsize=1)
def _pacote(caminho: str) -> dict:
    try:
        return joblib.load(caminho)
    except FileNotFoundError as e:
        raise ModeloIndisponivel(caminho) from e


def modelo_carregado() -> bool:
    try:
        _pacote(str(carregar().caminho_modelo))
        return True
    except ModeloIndisponivel:
        return False


def _prever_horas(pacote: dict, local: dict, dia: int, horas: list[int]) -> pd.DataFrame:
    df = pd.DataFrame({"local_id": local["id"], "categoria": perfil(local["categoria"])["categoria"], "dia_semana": dia, "hora": horas})
    notas = np.clip(pacote["modelo"].predict(matriz(df)), 1, 5)
    ajuste = pacote["ajuste_local"].get(int(local["id"]), 0.0)
    df[ALVOS] = notas
    df["nivel"] = np.clip(nivel_sobrecarga(notas[:, 0], notas[:, 1], notas[:, 2]) + ajuste, 0, 100)
    return df


def prever(local: dict, dia: int, hora: int) -> dict:
    try:
        pacote = _pacote(str(carregar().caminho_modelo))
    except ModeloIndisponivel:
        raise ErroApi(503, "SERVICO_INDISPONIVEL", "Modelo de previsão não encontrado. Rode python -m ml.treinar.")

    p = perfil(local["categoria"])  # tipo do Java (ex.: MUSEU) -> categoria do modelo + horário típico
    janela = p["horario"].get(dia)
    horas_dia = list(range(*janela)) if janela else []
    tabela = _prever_horas(pacote, local, dia, sorted(set(horas_dia + [hora])))
    linha = tabela[tabela["hora"] == hora].iloc[0]
    nivel = int(round(linha["nivel"]))

    melhor = None
    if horas_dia:
        no_horario = tabela[tabela["hora"].isin(horas_dia)]
        melhor_linha = no_horario.loc[no_horario["nivel"].idxmin()]
        melhor = {"hora": int(melhor_linha["hora"]), "nivel": int(round(melhor_linha["nivel"]))}

    alertas = []
    if linha["ruido"] >= LIMIAR_ALERTA:
        alertas.append("Barulho alto previsto nesse horário")
    if linha["luz"] >= LIMIAR_ALERTA:
        alertas.append("Luz forte prevista nesse horário")
    if linha["lotacao"] >= LIMIAR_ALERTA:
        alertas.append("Lugar cheio previsto nesse horário")
    if not (janela and janela[0] <= hora < janela[1]):
        alertas.append(f"Lugares desse tipo ({p['nome_tipo']}) costumam estar fechados nesse horário; confirme antes de ir")
    if int(local["id"]) not in pacote["ajuste_local"]:
        alertas.append("Este lugar ainda tem poucas avaliações; a previsão usa o padrão de lugares parecidos")

    k = cache.chave("previsao", local["id"], dia, hora)
    guardado = cache.obter(k)
    if guardado:
        return guardado

    dados = {
        "lugar": local["nome"],
        "tipo": p["nome_tipo"],
        "dia": NOMES_DIAS[dia],
        "hora": f"{hora}h",
        "faixa": TEXTO_FAIXA[faixa(nivel)],
        "alertas": alertas,
        "horario_mais_tranquilo_do_dia": f"{melhor['hora']}h" if melhor else "fechado nesse dia",
    }
    try:
        explicacao = llm.gerar(SISTEMA, json.dumps(dados, ensure_ascii=False), max_tokens=150, temperatura=0.4)
        gerado_por = "llm"
    except llm.LLMIndisponivel:
        explicacao = texto_padrao(local, dia, hora, nivel, melhor)
        gerado_por = "regra"

    resultado = {
        "nivelPrevisto": nivel,
        "faixa": faixa(nivel),
        "explicacao": explicacao,
        "melhorHorario": melhor["hora"] if melhor else None,
        "alertas": alertas,
        "geradoPor": gerado_por,
    }
    if gerado_por == "llm":
        cache.guardar(k, resultado)
    return resultado


def texto_padrao(local: dict, dia: int, hora: int, nivel: int, melhor: dict | None) -> str:
    """Frase sem IA, usada quando o LLM não responde (o app continua funcionando)."""
    dia_txt = NOMES_DIAS[dia].capitalize()
    frase = f"{dia_txt} às {hora}h, a previsão para {local['nome']} é de um ambiente {TEXTO_FAIXA[faixa(nivel)]}."
    if melhor and melhor["hora"] != hora and melhor["nivel"] <= nivel - 10:
        frase += f" Se puder, prefira ir por volta das {melhor['hora']}h, o horário mais tranquilo desse dia."
    elif faixa(nivel) == "TRANQUILO":
        frase += " É um bom horário para ir."
    elif not melhor:
        frase += " Esse tipo de lugar costuma estar fechado nesse dia."
    return frase
