"""Cliente do LLM por API compatível com OpenAI (/chat/completions).

Serve para Gemini (padrão), Groq, OpenAI e outros: muda só AI_BASE_URL e AI_MODEL.
Qualquer falha vira LLMIndisponivel (e fica registrada no log), e quem chama usa o texto
alternativo sem IA.

Diagnóstico: python -m app.llm   (faz uma chamada de teste e mostra o erro exato, se houver)
"""
import logging
import re
import time

import httpx

from .config import carregar

log = logging.getLogger("sereno.llm")

# Quando True, um 429 (limite de uso do provedor) espera e tenta de novo. A avaliação em lote liga;
# o serviço não, para o usuário nunca ficar esperando: ele recebe o texto alternativo na hora.
ESPERAR_LIMITE = False
MAX_TENTATIVAS = 6


class LLMIndisponivel(Exception):
    pass


def gerar(sistema: str, usuario: str, max_tokens: int = 400, temperatura: float = 0.2) -> str:
    cfg = carregar()
    if not cfg.ai_api_key:
        raise LLMIndisponivel("AI_API_KEY não configurada")
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            texto = _chamar(cfg, sistema, usuario, max_tokens, temperatura)
            break
        except LLMIndisponivel as e:
            espera = getattr(e, "esperar", None)
            if not (ESPERAR_LIMITE and espera is not None and tentativa < MAX_TENTATIVAS):
                log.warning("LLM falhou: %s", e)
                raise
            time.sleep(espera + 0.5)
    texto = (texto or "").strip()
    if not texto:
        raise LLMIndisponivel("resposta vazia do LLM (se for um modelo de raciocínio, aumente AI_MAX_TOKENS)")
    return texto


def _chamar(cfg, sistema, usuario, max_tokens, temperatura) -> str:
    corpo = {
        "model": cfg.ai_model,
        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
        "temperature": temperatura,
        "max_tokens": max(max_tokens, cfg.ai_max_tokens),
    }
    if cfg.ai_reasoning_effort:
        corpo["reasoning_effort"] = cfg.ai_reasoning_effort
    try:
        resposta = httpx.post(
            f"{cfg.ai_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {cfg.ai_api_key}", "User-Agent": "sereno-ia/1.0"},
            json=corpo,
            timeout=cfg.ai_timeout,
        )
        if resposta.status_code >= 400:
            erro = LLMIndisponivel(f"HTTP {resposta.status_code} em {cfg.ai_base_url}: {resposta.text[:300]}")
            if resposta.status_code == 429:
                erro.esperar = _segundos_de_espera(resposta)
            raise erro
        return resposta.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMIndisponivel(f"{type(e).__name__}: {e}") from e


def _segundos_de_espera(resposta) -> float:
    cabecalho = resposta.headers.get("retry-after")
    if cabecalho:
        try:
            return float(cabecalho)
        except ValueError:
            pass
    m = re.search(r"try again in ([\d.]+)s", resposta.text)
    return float(m.group(1)) if m else 10.0


def configurado() -> bool:
    return bool(carregar().ai_api_key)


if __name__ == "__main__":
    cfg = carregar()
    chave = cfg.ai_api_key
    print(f"AI_BASE_URL = {cfg.ai_base_url}")
    print(f"AI_MODEL    = {cfg.ai_model}")
    print(f"AI_API_KEY  = {chave[:4] + '…' + chave[-4:] if len(chave) > 8 else '(vazia ou curta demais)'}")
    print(f"AI_TIMEOUT  = {cfg.ai_timeout}s · AI_REASONING_EFFORT = {cfg.ai_reasoning_effort or '(não enviado)'}")
    try:
        inicio = time.perf_counter()
        print("Resposta do LLM:", gerar("Responda em uma frase curta.", "Diga 'olá, Sereno' em português."))
        print(f"OK: o LLM está funcionando ({time.perf_counter() - inicio:.1f}s).")
    except LLMIndisponivel as e:
        print("FALHOU:", e)
