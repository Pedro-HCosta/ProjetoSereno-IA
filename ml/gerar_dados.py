"""Gera o conjunto SINTÉTICO de avaliações usado no treino.

Por que sintético: o app ainda não tem volume de avaliações reais. Os padrões abaixo são
suposições documentadas do comportamento típico de cada tipo de lugar em São Paulo
(ex.: UBS cheia logo cedo, terminal cheio nos horários de pico, parque cheio no fim de semana).
Quando houver avaliações reais exportadas do Oracle, o treino as junta a este conjunto.

Uso: python -m ml.gerar_dados   (gera ml/dados/avaliacoes_sinteticas.csv)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.features import CATEGORIAS, HORARIO_TIPICO

RAIZ = Path(__file__).resolve().parent
SEMENTE = 2026
VISITAS_POR_LOCAL = 250
LOCAIS_EXTRAS_POR_CATEGORIA = 3  # lugares sintéticos além dos 6 do catálogo, para o modelo generalizar


def _pico(h, centro, altura, largura):
    return altura * np.exp(-(((h - centro) / largura) ** 2))


def lotacao_esperada(cat: str, dia: int, h: float) -> float:
    """Lotação típica de 0 a 1 por categoria, dia (0 = domingo) e hora."""
    util, sab, dom = 1 <= dia <= 5, dia == 6, dia == 0
    if cat == "SAUDE":  # UBS: fila na abertura, segundo pico após o almoço; segunda é o pior dia
        v = _pico(h, 8, 0.9, 1.5) + _pico(h, 14, 0.5, 1.5)
        v *= {1: 1.15, 5: 0.9}.get(dia, 1.0) if util else 0.6
    elif cat == "MERCADO":  # almoço e saída do trabalho; manhã de fim de semana
        if util:
            v = 0.15 + _pico(h, 12, 0.55, 1.2) + _pico(h, 18.5, 0.8, 1.5)
        elif sab:
            v = 0.2 + _pico(h, 11, 0.75, 2.5) + _pico(h, 16, 0.6, 2.0)
        else:
            v = 0.15 + _pico(h, 10, 0.8, 1.8) + _pico(h, 17, 0.25, 2.0)
    elif cat == "TRANSPORTE":  # horários de pico nos dias úteis
        if util:
            v = 0.2 + _pico(h, 7.5, 0.85, 1.2) + _pico(h, 18, 0.8, 1.3)
        elif sab:
            v = 0.2 + _pico(h, 13, 0.3, 3.0)
        else:
            v = 0.15 + _pico(h, 15, 0.25, 2.5)
    elif cat == "LAZER":  # parque: corredores cedo e no fim da tarde; lotado no fim de semana
        if util:
            v = 0.1 + _pico(h, 7, 0.35, 1.2) + _pico(h, 18, 0.4, 1.5)
        else:
            v = 0.15 + _pico(h, 11, 0.75, 2.5) + _pico(h, 16, 0.7, 2.0)
    elif cat == "SERVICO_PUBLICO":  # Poupatempo: manhã cheia, segunda-feira pior
        v = _pico(h, 9.5, 0.95, 1.8) + _pico(h, 14, 0.6, 1.5) if util else _pico(h, 9, 0.7, 1.5)
        v *= 1.1 if dia == 1 else 1.0
    else:  # EDUCACAO — biblioteca: tarde e começo da noite moderados, manhã calma
        v = 0.1 + (_pico(h, 15, 0.55, 2.5) + _pico(h, 19, 0.4, 1.2) if util else _pico(h, 13, 0.5, 2.5))
    return float(np.clip(v, 0, 1))


RUIDO_BASE = {"TRANSPORTE": 0.5, "MERCADO": 0.35, "SAUDE": 0.2, "SERVICO_PUBLICO": 0.2, "LAZER": 0.1, "EDUCACAO": 0.0}
LUZ_BASE = {"SAUDE": 0.55, "MERCADO": 0.6, "SERVICO_PUBLICO": 0.5, "EDUCACAO": 0.3, "TRANSPORTE": 0.45}


def luz_esperada(cat: str, h: float, lot: float) -> float:
    if cat == "LAZER":  # ao ar livre: luz do sol forte perto do meio-dia
        return 0.2 + _pico(h, 12.5, 0.7, 2.5)
    return LUZ_BASE[cat] + 0.15 * lot  # ambiente fechado: iluminação artificial quase constante


def _nota(valor_0a1, ruido, rng):
    return int(np.clip(np.rint(1 + 4 * valor_0a1 + rng.normal(0, ruido)), 1, 5))


def gerar(semente: int = SEMENTE) -> pd.DataFrame:
    rng = np.random.default_rng(semente)
    catalogo = json.loads((RAIZ / "dados" / "locais.json").read_text(encoding="utf-8"))
    locais = [(l["id"], l["categoria"]) for l in catalogo]
    prox = 101
    for cat in CATEGORIAS:
        for _ in range(LOCAIS_EXTRAS_POR_CATEGORIA):
            locais.append((prox, cat))
            prox += 1

    linhas = []
    for local_id, cat in locais:
        fator_lotacao = rng.normal(1.0, 0.15)  # alguns lugares são mais movimentados que outros
        ajuste_luz = rng.normal(0, 0.08)
        dias = sorted(HORARIO_TIPICO[cat])
        # Mais visitas (e avaliações) quando o lugar está cheio, como na vida real
        opcoes = [(d, h) for d in dias for h in range(*HORARIO_TIPICO[cat][d])]
        pesos = np.array([0.3 + lotacao_esperada(cat, d, h + 0.5) for d, h in opcoes])
        escolhas = rng.choice(len(opcoes), size=VISITAS_POR_LOCAL, p=pesos / pesos.sum())
        for i in escolhas:
            dia, hora = opcoes[i]
            h = hora + rng.uniform(0, 1)
            lot = float(np.clip(lotacao_esperada(cat, dia, h) * fator_lotacao, 0, 1))
            linhas.append({
                "local_id": local_id,
                "categoria": cat,
                "dia_semana": dia,
                "hora": hora,
                "ruido": _nota(0.25 * RUIDO_BASE[cat] + 0.75 * lot, 0.6, rng),
                "luz": _nota(float(np.clip(luz_esperada(cat, h, lot) + ajuste_luz, 0, 1)), 0.5, rng),
                "lotacao": _nota(lot, 0.5, rng),
                "fonte": "sintetico",
            })
    return pd.DataFrame(linhas)


if __name__ == "__main__":
    df = gerar()
    destino = RAIZ / "dados" / "avaliacoes_sinteticas.csv"
    df.to_csv(destino, index=False)
    print(f"{len(df)} avaliações sintéticas de {df['local_id'].nunique()} lugares → {destino}")
