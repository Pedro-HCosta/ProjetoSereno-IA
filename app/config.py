"""Configuração do serviço, lida só de variáveis de ambiente (nada de segredo no código)."""
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

try:  # .env só para desenvolvimento local; na Azure as variáveis vêm das App Settings
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Config:
    jwt_secret: str
    jwt_issuer: str
    jwt_audience: str
    jwt_secret_base64: bool
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_timeout: float
    ai_max_tokens: int
    ai_reasoning_effort: str
    java_api_url: str
    java_timeout: float
    caminho_modelo: Path
    caminho_indice: Path
    caminho_locais: Path


def carregar() -> Config:
    return Config(
        jwt_secret=os.getenv("JWT_SECRET", ""),
        jwt_issuer=os.getenv("JWT_ISSUER", "sereno-auth"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "sereno-app"),
        # false (padrão) = segredo lido como texto UTF-8, igual ao .NET (Encoding.UTF8.GetBytes).
        # true = o segredo é Base64 e a chave são os bytes decodificados (ex.: Java com Decoders.BASE64).
        jwt_secret_base64=os.getenv("JWT_SECRET_BASE64", "false").strip().lower() in ("1", "true", "sim"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        # Qualquer provedor com API compatível com OpenAI (Gemini, Groq, OpenAI...)
        ai_base_url=os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"),
        ai_model=os.getenv("AI_MODEL", "gemini-2.5-flash"),
        # Tempo máximo esperando o LLM: a pessoa está olhando a tela; passou disso, vai o texto alternativo
        ai_timeout=float(os.getenv("AI_TIMEOUT", "10")),
        # Modelos de raciocínio (gpt-oss, Gemini 2.5) gastam tokens "pensando" antes de responder:
        # o limite precisa ser folgado, senão a resposta sai vazia. O tamanho do texto é controlado pelo prompt.
        ai_max_tokens=int(os.getenv("AI_MAX_TOKENS", "2048")),
        # low = o modelo "pensa" menos: resposta mais rápida e menos tokens. Vazio = não envia
        # (use vazio em modelos sem raciocínio, como gpt-4o-mini, que recusam o parâmetro).
        ai_reasoning_effort=os.getenv("AI_REASONING_EFFORT", "").strip(),
        java_api_url=os.getenv("JAVA_API_URL", "").rstrip("/"),
        # A API Java no plano gratuito do Render "dorme" e leva dezenas de segundos para acordar
        java_timeout=float(os.getenv("JAVA_TIMEOUT", "8")),
        caminho_modelo=Path(os.getenv("MODELO_PATH", RAIZ / "ml" / "modelo" / "modelo_previsao.joblib")),
        caminho_indice=Path(os.getenv("INDICE_PATH", RAIZ / "rag" / "indice")),
        caminho_locais=Path(os.getenv("LOCAIS_PATH", RAIZ / "ml" / "dados" / "locais.json")),
    )
