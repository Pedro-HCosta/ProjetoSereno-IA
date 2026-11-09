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
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_timeout: float
    java_api_url: str
    caminho_modelo: Path
    caminho_indice: Path
    caminho_locais: Path


def carregar() -> Config:
    return Config(
        jwt_secret=os.getenv("JWT_SECRET", ""),
        jwt_issuer=os.getenv("JWT_ISSUER", "sereno-auth"),
        jwt_audience=os.getenv("JWT_AUDIENCE", "sereno-app"),
        ai_api_key=os.getenv("AI_API_KEY", ""),
        # Qualquer provedor com API compatível com OpenAI (Gemini, Groq, OpenAI...)
        ai_base_url=os.getenv("AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"),
        ai_model=os.getenv("AI_MODEL", "gemini-2.5-flash"),
        ai_timeout=float(os.getenv("AI_TIMEOUT", "15")),
        java_api_url=os.getenv("JAVA_API_URL", "").rstrip("/"),
        caminho_modelo=Path(os.getenv("MODELO_PATH", RAIZ / "ml" / "modelo" / "modelo_previsao.joblib")),
        caminho_indice=Path(os.getenv("INDICE_PATH", RAIZ / "rag" / "indice")),
        caminho_locais=Path(os.getenv("LOCAIS_PATH", RAIZ / "ml" / "dados" / "locais.json")),
    )
