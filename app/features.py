"""Features do modelo de previsão — usadas igualzinho no treino (ml/treinar.py) e no serviço."""
import numpy as np
import pandas as pd

CATEGORIAS = ["SAUDE", "MERCADO", "TRANSPORTE", "LAZER", "SERVICO_PUBLICO", "EDUCACAO"]

# Funcionamento típico por categoria: {dia (0=domingo): (abre, fecha)}; dia ausente = fechado
HORARIO_TIPICO = {
    "SAUDE": {d: (7, 19) for d in range(1, 6)} | {6: (7, 12)},
    "MERCADO": {d: (7, 22) for d in range(7)},
    "TRANSPORTE": {d: (5, 23) for d in range(7)},
    "LAZER": {d: (5, 22) for d in range(7)},
    "SERVICO_PUBLICO": {d: (7, 19) for d in range(1, 6)} | {6: (7, 13)},
    "EDUCACAO": {d: (8, 20) for d in range(1, 6)} | {6: (9, 17)},
}

ALVOS = ["ruido", "luz", "lotacao"]  # notas de 1 a 5, como no formulário de avaliação


def aberto(categoria: str, dia: int, hora: int) -> bool:
    janela = HORARIO_TIPICO.get(categoria, {}).get(dia)
    return bool(janela) and janela[0] <= hora < janela[1]


def nivel_sobrecarga(ruido, luz, lotacao):
    """Média das três notas (1–5) levada para 0–100: 0 = tudo calmo, 100 = tudo no máximo."""
    media = (np.asarray(ruido, dtype=float) + np.asarray(luz, dtype=float) + np.asarray(lotacao, dtype=float)) / 3
    return np.clip((media - 1) / 4 * 100, 0, 100)


def matriz(df: pd.DataFrame) -> pd.DataFrame:
    """df precisa de: categoria, dia_semana (0–6), hora (0–23).

    O lugar específico NÃO entra aqui: o modelo aprende o padrão do TIPO de lugar e, depois,
    cada lugar recebe um ajuste próprio (ajuste_local, calculado no treino). Assim um lugar
    recém-cadastrado já tem previsão pela categoria.
    """
    x = pd.DataFrame(index=df.index)
    x["hora"] = df["hora"].astype(int)
    x["dia_semana"] = df["dia_semana"].astype(int)
    x["fim_de_semana"] = x["dia_semana"].isin([0, 6]).astype(int)
    for c in CATEGORIAS:
        x[f"cat_{c}"] = (df["categoria"] == c).astype(int)
    return x


def faixa(nivel: float) -> str:
    if nivel < 40:
        return "TRANQUILO"
    if nivel < 70:
        return "MODERADO"
    return "AGITADO"
