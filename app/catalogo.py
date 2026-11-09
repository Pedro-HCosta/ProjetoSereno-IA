"""Descobre nome e categoria de um local.

1º tenta a API Java (fonte oficial dos lugares), repassando o token do usuário;
2º usa o catálogo local ml/dados/locais.json (mesmos lugares do seed), se a API não responder.
"""
import json
from functools import lru_cache

import httpx

from .config import carregar
from .erros import ErroApi


@lru_cache(maxsize=1)
def _catalogo_local(caminho: str) -> dict[int, dict]:
    with open(caminho, encoding="utf-8") as f:
        return {int(l["id"]): l for l in json.load(f)}


def buscar_local(local_id: int, token: str | None) -> dict:
    cfg = carregar()
    if cfg.java_api_url and token:
        try:
            r = httpx.get(
                f"{cfg.java_api_url}/api/locais/{local_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=3,
            )
            if r.status_code == 200:
                d = r.json()
                return {"id": local_id, "nome": d.get("nome", f"Local {local_id}"), "categoria": str(d["categoria"]).upper()}
            if r.status_code == 404:
                raise ErroApi(404, "NAO_ENCONTRADO", f"Local {local_id} não encontrado")
        except (httpx.HTTPError, KeyError, ValueError):
            pass  # API Java fora do ar → cai no catálogo local

    local = _catalogo_local(str(cfg.caminho_locais)).get(local_id)
    if not local:
        raise ErroApi(404, "NAO_ENCONTRADO", f"Local {local_id} não encontrado")
    return local
