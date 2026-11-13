"""Descobre nome e tipo de um local.

1º tenta a API Java (fonte oficial dos lugares), repassando o token do usuário;
2º usa o catálogo local ml/dados/locais.json (mesmos lugares do exemplo), se a API não responder.

O tipo do Java (PARQUE, MUSEU, SHOPPING...) é traduzido para a categoria do modelo em features.perfil().
"""
import json
import logging
from functools import lru_cache

import httpx

from . import cache
from .config import carregar
from .erros import ErroApi

log = logging.getLogger("sereno.catalogo")


@lru_cache(maxsize=1)
def _catalogo_local(caminho: str) -> dict[int, dict]:
    with open(caminho, encoding="utf-8") as f:
        return {int(l["id"]): l for l in json.load(f)}


def buscar_local(local_id: int, token: str | None) -> dict:
    cfg = carregar()
    java_falhou = False
    if cfg.java_api_url and token:
        k = cache.chave("local", local_id)
        guardado = cache.obter(k)
        if guardado:
            return guardado
        try:
            r = httpx.get(
                f"{cfg.java_api_url}/api/locais/{local_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=cfg.java_timeout,
            )
            if r.status_code == 200:
                d = r.json()
                local = {"id": local_id, "nome": d.get("nome") or f"Local {local_id}", "categoria": str(d.get("categoria") or "OUTRO")}
                cache.guardar(k, local)
                return local
            if r.status_code == 404:
                raise ErroApi(404, "NAO_ENCONTRADO", f"Local {local_id} não encontrado")
            log.warning("API Java respondeu %s para o local %s", r.status_code, local_id)
            java_falhou = True
        except (httpx.HTTPError, ValueError) as e:
            log.warning("API Java indisponível (%s): usando o catálogo local", type(e).__name__)
            java_falhou = True

    local = _catalogo_local(str(cfg.caminho_locais)).get(local_id)
    if local:
        return local
    if java_falhou:  # o lugar pode existir no Java: não dizer "não encontrado" por causa de uma falha de rede
        raise ErroApi(503, "SERVICO_INDISPONIVEL", "Não foi possível consultar os lugares agora. Tente de novo em instantes.")
    raise ErroApi(404, "NAO_ENCONTRADO", f"Local {local_id} não encontrado")
