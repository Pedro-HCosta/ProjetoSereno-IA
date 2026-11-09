"""Serviço de IA do Sereno — base /ia (Contrato compartilhado).

POST /ia/previsao-calma  previsão de sobrecarga sensorial + frase do LLM
POST /ia/direitos        RAG sobre leis de acessibilidade + resposta do LLM citando artigos
GET  /ia/health          público
"""
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from . import direitos, erros, llm, previsao
from .auth import usuario_logado
from .catalogo import buscar_local
from .schemas import DireitosRequest, DireitosResponse, PrevisaoRequest, PrevisaoResponse

app = FastAPI(
    title="Sereno — Serviço de IA",
    version="1.0.0",
    description="Previsão do horário calmo (ML + LLM) e orientação sobre direitos de acessibilidade (RAG).",
    docs_url="/ia/docs",
    openapi_url="/ia/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
erros.registrar(app)

ERROS_DOC = {400: {"description": "Dados inválidos"}, 401: {"description": "Token ausente, inválido ou expirado"}}


@app.get("/ia/health", tags=["monitoramento"])
def health():
    componentes = {
        "modelo_previsao": "UP" if previsao.modelo_carregado() else "DOWN",
        "indice_leis": "UP" if direitos.indice_carregado() else "DOWN",
        "llm": "CONFIGURADO" if llm.configurado() else "SEM_CHAVE",  # sem chave o serviço usa o texto alternativo
    }
    status = "UP" if componentes["modelo_previsao"] == "UP" and componentes["indice_leis"] == "UP" else "DEGRADED"
    return {"status": status, "componentes": componentes}


@app.post("/ia/previsao-calma", response_model=PrevisaoResponse, tags=["previsão"],
          responses=ERROS_DOC | {404: {"description": "Local não encontrado"}})
def previsao_calma(corpo: PrevisaoRequest, request: Request, usuario: dict = Depends(usuario_logado)):
    local = buscar_local(corpo.localId, getattr(request.state, "token", None))
    return previsao.prever(local, corpo.diaSemana, corpo.hora)


@app.post("/ia/direitos", response_model=DireitosResponse, tags=["direitos"], responses=ERROS_DOC)
def direitos_acessibilidade(corpo: DireitosRequest, usuario: dict = Depends(usuario_logado)):
    return direitos.responder(corpo.situacao, corpo.contexto)
