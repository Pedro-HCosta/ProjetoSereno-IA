"""Monta o índice vetorial das leis.

1. Salve no navegador (Ctrl+S, "somente HTML") as páginas oficiais do Planalto em rag/leis/:
   l13146.htm, l10098.htm, l12764.htm (links no README).
2. Rode: python -m rag.indexar
Saída: rag/indice/leis.faiss, vetorizador.joblib, trechos.json
"""
from collections import Counter
from pathlib import Path

from app.rag_motor import construir_indice, dividir_por_artigo, identificar_lei, texto_da_lei

RAIZ = Path(__file__).resolve().parent


def main(pasta_leis: Path = RAIZ / "leis", destino: Path = RAIZ / "indice") -> None:
    arquivos = sorted(p for p in pasta_leis.iterdir() if p.suffix.lower() in (".htm", ".html", ".txt"))
    if not arquivos:
        raise SystemExit(f"Nenhuma lei encontrada em {pasta_leis}. Veja as instruções no topo deste arquivo.")
    trechos = []
    for arq in arquivos:
        texto = texto_da_lei(arq)
        meta = identificar_lei(arq, texto)
        partes = dividir_por_artigo(texto, meta)
        artigos = len({p["artigo"] for p in partes})
        print(f"{meta['lei']}: {artigos} artigos, {len(partes)} trechos ({arq.name})")
        trechos += partes
    total = construir_indice(trechos, destino)
    print(f"Índice criado com {total} trechos em {destino}")
    print("Trechos por lei:", dict(Counter(t["lei"] for t in trechos)))


if __name__ == "__main__":
    main()
