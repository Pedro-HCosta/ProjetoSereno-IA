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

# Tipos de lugar que chegam da API Java (12) ou do catálogo local. O modelo foi treinado com as 6
# CATEGORIAS acima; cada tipo usa a categoria de comportamento mais parecido, mas mantém o próprio
# horário de funcionamento e o próprio nome no texto. Tipo desconhecido cai em OUTRO (nunca dá erro).
#   tipo: (categoria do modelo, horário {dia: (abre, fecha)}, nome no texto)
_TODO_DIA = range(7)
TIPOS = {
    "SAUDE": ("SAUDE", HORARIO_TIPICO["SAUDE"], "unidade de saúde"),
    "MERCADO": ("MERCADO", HORARIO_TIPICO["MERCADO"], "mercado"),
    "TRANSPORTE": ("TRANSPORTE", HORARIO_TIPICO["TRANSPORTE"], "terminal de transporte"),
    "LAZER": ("LAZER", HORARIO_TIPICO["LAZER"], "espaço de lazer"),
    "SERVICO_PUBLICO": ("SERVICO_PUBLICO", HORARIO_TIPICO["SERVICO_PUBLICO"], "posto de serviço público"),
    "EDUCACAO": ("EDUCACAO", HORARIO_TIPICO["EDUCACAO"], "espaço de educação"),
    "PARQUE": ("LAZER", HORARIO_TIPICO["LAZER"], "parque"),
    "BIBLIOTECA": ("EDUCACAO", HORARIO_TIPICO["EDUCACAO"], "biblioteca"),
    "MUSEU": ("EDUCACAO", {d: (10, 18) for d in range(7) if d != 1}, "museu"),  # fecha às segundas
    "CENTRO_CULTURAL": ("LAZER", {d: (10, 21) for d in range(7) if d != 1}, "centro cultural"),
    "SHOPPING": ("MERCADO", {d: (10, 22) for d in _TODO_DIA}, "shopping"),
    "RESTAURANTE": ("MERCADO", {d: (11, 23) for d in _TODO_DIA}, "restaurante"),
    "CAFE": ("MERCADO", {d: (7, 20) for d in _TODO_DIA}, "café"),
    "OUTRO": ("LAZER", {d: (8, 20) for d in _TODO_DIA}, "lugar"),
}


def perfil(tipo: str) -> dict:
    """Categoria do modelo, horário e nome para um tipo de lugar (tipo desconhecido = OUTRO)."""
    chave = str(tipo).strip().upper().replace(" ", "_").replace("-", "_")
    categoria, horario, nome = TIPOS.get(chave, TIPOS["OUTRO"])
    return {"tipo": chave if chave in TIPOS else "OUTRO", "categoria": categoria, "horario": horario, "nome_tipo": nome}


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
