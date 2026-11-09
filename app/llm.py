"""Cliente do LLM por API compatível com OpenAI (/chat/completions).

Serve para Gemini (padrão), Groq, OpenAI e outros: muda só AI_BASE_URL e AI_MODEL.
Qualquer falha vira LLMIndisponivel, e quem chama usa o texto alternativo sem IA.
"""
import httpx

from .config import carregar


class LLMIndisponivel(Exception):
    pass


def gerar(sistema: str, usuario: str, max_tokens: int = 400, temperatura: float = 0.2) -> str:
    cfg = carregar()
    if not cfg.ai_api_key:
        raise LLMIndisponivel("AI_API_KEY não configurada")
    try:
        resposta = httpx.post(
            f"{cfg.ai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.ai_api_key}"},
            json={
                "model": cfg.ai_model,
                "messages": [
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": usuario},
                ],
                "temperature": temperatura,
                "max_tokens": max_tokens,
            },
            timeout=cfg.ai_timeout,
        )
        resposta.raise_for_status()
        texto = resposta.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMIndisponivel(str(e)) from e
    texto = (texto or "").strip()
    if not texto:
        raise LLMIndisponivel("resposta vazia do LLM")
    return texto


def configurado() -> bool:
    return bool(carregar().ai_api_key)
