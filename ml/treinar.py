"""Treina o modelo de previsão de sobrecarga sensorial e mede contra linhas de base.

Uso: python -m ml.treinar
Entrada: ml/dados/avaliacoes_sinteticas.csv (+ ml/dados/avaliacoes_oracle.csv, se existir)
Saída:   ml/modelo/modelo_previsao.joblib, ml/modelo/metricas.json, ml/RESULTADOS.md
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

from app.features import ALVOS, CATEGORIAS, matriz, nivel_sobrecarga

RAIZ = Path(__file__).resolve().parent
SEMENTE = 42
PARAMS = {"n_estimators": 200, "min_samples_leaf": 5, "max_features": 0.6, "random_state": SEMENTE, "n_jobs": -1}
# Ajuste do lugar = soma dos resíduos / (nº de avaliações + ENCOLHIMENTO): com poucas avaliações o ajuste fica perto de 0
ENCOLHIMENTO = 20


def carregar_dados() -> pd.DataFrame:
    df = pd.read_csv(RAIZ / "dados" / "avaliacoes_sinteticas.csv")
    real = RAIZ / "dados" / "avaliacoes_oracle.csv"
    if real.exists():
        # Exportação do Oracle: local_id, categoria, data_hora_visita, ruido, luminosidade, lotacao
        r = pd.read_csv(real, parse_dates=["data_hora_visita"])
        r = pd.DataFrame({
            "local_id": r["local_id"],
            "categoria": r["categoria"].str.upper(),
            "dia_semana": (r["data_hora_visita"].dt.dayofweek + 1) % 7,  # pandas: 0 = segunda → 0 = domingo
            "hora": r["data_hora_visita"].dt.hour,
            "ruido": r["ruido"],
            "luz": r["luminosidade"],
            "lotacao": r["lotacao"],
            "fonte": "oracle",
        })
        df = pd.concat([df, r[r["categoria"].isin(CATEGORIAS)]], ignore_index=True)
    df["nivel"] = nivel_sobrecarga(df["ruido"], df["luz"], df["lotacao"])
    return df


def treinar(treino: pd.DataFrame):
    """Random Forest com as três notas como saída + ajuste próprio de cada lugar."""
    modelo = RandomForestRegressor(**PARAMS)
    modelo.fit(matriz(treino), treino[ALVOS])
    previsto, _ = prever_nivel(modelo, treino, {})
    residuos = pd.DataFrame({"local_id": treino["local_id"], "r": treino["nivel"].to_numpy() - previsto})
    g = residuos.groupby("local_id")["r"].agg(["sum", "count"])
    ajuste_local = {int(k): round(float(v), 2) for k, v in (g["sum"] / (g["count"] + ENCOLHIMENTO)).items()}
    return modelo, ajuste_local


def prever_nivel(modelo, df, ajuste_local):
    notas = np.clip(modelo.predict(matriz(df)), 1, 5)
    ajuste = df["local_id"].map(lambda i: ajuste_local.get(int(i), 0.0)).to_numpy(dtype=float)
    return np.clip(nivel_sobrecarga(notas[:, 0], notas[:, 1], notas[:, 2]) + ajuste, 0, 100), notas


def baseline_media_geral(treino, teste):
    return np.full(len(teste), treino["nivel"].mean())


def baseline_categoria_hora(treino, teste):
    chave = lambda d: list(zip(d["categoria"], d["dia_semana"].isin([0, 6]), d["hora"]))
    tabela = treino.assign(k=chave(treino)).groupby("k")["nivel"].mean().to_dict()
    por_cat = treino.groupby("categoria")["nivel"].mean().to_dict()
    return np.array([tabela.get(k, por_cat[k[0]]) for k in chave(teste)])


def metricas(y, p):
    return {"MAE": round(float(mean_absolute_error(y, p)), 2), "R2": round(float(r2_score(y, p)), 3)}


def avaliar(treino, teste, rotulo):
    modelo, ajuste = treinar(treino)
    nivel, notas = prever_nivel(modelo, teste, ajuste)
    r = {
        "cenario": rotulo,
        "linhas_treino": int(len(treino)),
        "linhas_teste": int(len(teste)),
        "modelo": metricas(teste["nivel"], nivel),
        "baseline_media_geral": metricas(teste["nivel"], baseline_media_geral(treino, teste)),
        "baseline_categoria_hora": metricas(teste["nivel"], baseline_categoria_hora(treino, teste)),
        "MAE_por_nota_1a5": {a: round(float(mean_absolute_error(teste[a], notas[:, i])), 2) for i, a in enumerate(ALVOS)},
    }
    return r


def checagens_de_bom_senso(modelo, ajuste):
    """Casos que qualquer pessoa reconhece: o modelo precisa acertar a direção."""
    casos = [
        ("UBS: segunda 8h deve ser mais cheia que segunda 16h", 1, "SAUDE", (1, 8), (1, 16)),
        ("Terminal: quarta 18h mais cheio que domingo 18h", 3, "TRANSPORTE", (3, 18), (0, 18)),
        ("Parque: sábado 11h mais cheio que terça 11h", 4, "LAZER", (6, 11), (2, 11)),
        ("Poupatempo: segunda 10h mais cheio que sexta 17h", 5, "SERVICO_PUBLICO", (1, 10), (5, 17)),
        ("Biblioteca: terça 9h mais calma que terça 15h", 6, "EDUCACAO", (2, 15), (2, 9)),
    ]
    saida = []
    for desc, lid, cat, cheio, vazio in casos:
        df = pd.DataFrame([{"local_id": lid, "categoria": cat, "dia_semana": d, "hora": h} for d, h in (cheio, vazio)])
        n, _ = prever_nivel(modelo, df, ajuste)
        saida.append({"caso": desc, "cheio": round(float(n[0])), "vazio": round(float(n[1])), "ok": bool(n[0] > n[1])})
    return saida


def main():
    df = carregar_dados()

    # Cenário 1: 20% das avaliações separadas para teste (lugares conhecidos)
    treino, teste = train_test_split(df, test_size=0.2, random_state=SEMENTE, stratify=df["categoria"])
    aleatorio = avaliar(treino, teste, "teste aleatório (20% das avaliações)")

    # Cenário 2: lugares que o modelo nunca viu (1 lugar sintético por categoria fica de fora)
    fora = df[df["local_id"] >= 101].groupby("categoria")["local_id"].min().tolist()
    lugares_novos = avaliar(df[~df["local_id"].isin(fora)], df[df["local_id"].isin(fora)], "lugares novos (nunca vistos)")

    # Modelo final: treinado com tudo
    modelo, ajuste_local = treinar(df)
    bom_senso = checagens_de_bom_senso(modelo, ajuste_local)

    destino = RAIZ / "modelo"
    destino.mkdir(exist_ok=True)
    joblib.dump(
        {
            "modelo": modelo,
            "ajuste_local": ajuste_local,
            "treinado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "linhas": int(len(df)),
            "fontes": df["fonte"].value_counts().to_dict(),
        },
        destino / "modelo_previsao.joblib",
        compress=3,
    )
    resultado = {
        "parametros": {k: v for k, v in PARAMS.items() if k != "n_jobs"} | {"encolhimento_ajuste_local": ENCOLHIMENTO},
        "dados": {"linhas": int(len(df)), "lugares": int(df["local_id"].nunique()), "fontes": df["fonte"].value_counts().to_dict()},
        "cenarios": [aleatorio, lugares_novos],
        "bom_senso": bom_senso,
    }
    (destino / "metricas.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    escrever_resultados(resultado)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


def escrever_resultados(r):
    linhas = [
        "# Resultados do modelo de previsão",
        "",
        "Gerado por `python -m ml.treinar`. Alvo: nível de sobrecarga de 0 a 100 (média de ruído, luz e lotação).",
        f"Dados: {r['dados']['linhas']} avaliações de {r['dados']['lugares']} lugares — fontes: {r['dados']['fontes']}.",
        "",
        "| Cenário | Modelo (MAE / R²) | Média geral (MAE / R²) | Média por categoria e hora (MAE / R²) |",
        "| --- | --- | --- | --- |",
    ]
    for c in r["cenarios"]:
        f = lambda m: f"{m['MAE']} / {m['R2']}"
        linhas.append(f"| {c['cenario']} | **{f(c['modelo'])}** | {f(c['baseline_media_geral'])} | {f(c['baseline_categoria_hora'])} |")
    linhas += ["", "MAE em pontos da escala 0–100 (menor é melhor). R² = quanto da variação o modelo explica (1 = tudo).", "",
               "## Checagens de bom senso", "", "| Caso | Previsto (cheio) | Previsto (vazio) | Resultado |", "| --- | --- | --- | --- |"]
    for b in r["bom_senso"]:
        linhas.append(f"| {b['caso']} | {b['cheio']} | {b['vazio']} | {'ok' if b['ok'] else 'FALHOU'} |")
    (RAIZ / "RESULTADOS.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
