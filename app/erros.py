"""Erro padrão do Contrato: { status, erro, mensagem, campos, timestamp, path } — igual à API .NET."""
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErroApi(Exception):
    def __init__(self, status: int, erro: str, mensagem: str, campos: list[dict] | None = None):
        super().__init__(mensagem)
        self.status = status
        self.erro = erro
        self.mensagem = mensagem
        self.campos = campos or []


def corpo_erro(status: int, erro: str, mensagem: str, path: str, campos: list[dict] | None = None) -> dict:
    return {
        "status": status,
        "erro": erro,
        "mensagem": mensagem,
        "campos": campos or [],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "path": path,
    }


_CODIGOS = {401: "NAO_AUTENTICADO", 403: "ACESSO_NEGADO", 404: "NAO_ENCONTRADO", 405: "METODO_NAO_PERMITIDO"}


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErroApi)
    async def _erro_api(request: Request, exc: ErroApi):
        return JSONResponse(
            status_code=exc.status,
            content=corpo_erro(exc.status, exc.erro, exc.mensagem, request.url.path, exc.campos),
        )

    @app.exception_handler(RequestValidationError)
    async def _validacao(request: Request, exc: RequestValidationError):
        campos = []
        for e in exc.errors():
            nome = ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path"))
            campos.append({"campo": nome or "corpo", "mensagem": _traduzir(e)})
        return JSONResponse(
            status_code=400,
            content=corpo_erro(400, "VALIDACAO", "Dados inválidos", request.url.path, campos),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        erro = _CODIGOS.get(exc.status_code, "ERRO")
        mensagem = "Rota não encontrada" if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=corpo_erro(exc.status_code, erro, mensagem, request.url.path))

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):  # pragma: no cover - rede de segurança
        return JSONResponse(
            status_code=500,
            content=corpo_erro(500, "ERRO_INTERNO", "Erro inesperado no serviço de IA", request.url.path),
        )


def _traduzir(e: dict) -> str:
    tipo = e.get("type", "")
    ctx = e.get("ctx") or {}
    if tipo == "missing":
        return "é obrigatório"
    if tipo in ("string_too_short",):
        return f"deve ter pelo menos {ctx.get('min_length')} caracteres"
    if tipo in ("string_too_long",):
        return f"deve ter no máximo {ctx.get('max_length')} caracteres"
    if tipo in ("int_parsing", "int_type"):
        return "deve ser um número inteiro"
    if tipo in ("greater_than_equal",):
        return f"deve ser maior ou igual a {ctx.get('ge')}"
    if tipo == "value_error":
        return str(ctx.get("error", e.get("msg", "valor inválido")))
    return e.get("msg", "valor inválido")
