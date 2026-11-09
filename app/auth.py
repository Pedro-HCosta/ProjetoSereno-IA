"""Validação do JWT emitido pela API Java (mesmo segredo, iss e aud do Contrato compartilhado)."""
import jwt
from fastapi import Request

from .config import carregar
from .erros import ErroApi


def usuario_logado(request: Request) -> dict:
    """Dependência do FastAPI: devolve {id, email, papel} ou responde 401 no formato padrão."""
    cfg = carregar()
    if len(cfg.jwt_secret) < 32:
        raise ErroApi(500, "ERRO_INTERNO", "JWT_SECRET não configurado no serviço de IA (mínimo 32 caracteres)")

    cabecalho = request.headers.get("Authorization", "")
    if not cabecalho.lower().startswith("bearer "):
        raise ErroApi(401, "NAO_AUTENTICADO", "Token ausente. Faça login no app.")
    token = cabecalho.split(" ", 1)[1].strip()

    try:
        dados = jwt.decode(
            token,
            cfg.jwt_secret,
            algorithms=["HS256"],
            issuer=cfg.jwt_issuer,
            audience=cfg.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError:
        raise ErroApi(401, "NAO_AUTENTICADO", "Sessão expirada. Faça login novamente.")
    except jwt.InvalidTokenError:
        raise ErroApi(401, "NAO_AUTENTICADO", "Token inválido.")

    request.state.token = token  # repassado à API Java ao buscar o local
    return {"id": str(dados["sub"]), "email": dados.get("email"), "papel": dados.get("role")}
