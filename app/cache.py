"""Cache em memória com validade, para não pagar (em tempo e em tokens) a mesma pergunta duas vezes.

A previsão de um lugar num dia e hora e a resposta de direitos para a mesma situação não mudam de
um minuto para o outro. Na prática, o botão "Quais são meus direitos?" de uma estação manda sempre
o mesmo contexto: a partir da segunda pessoa, a resposta sai na hora e sem gastar tokens.
Só respostas geradas pelo LLM entram no cache; o texto alternativo (quando o LLM falha) não,
para que a próxima chamada tente o LLM de novo.
"""
import os
import re
import threading
import time
import unicodedata
from collections import OrderedDict

_TTL = float(os.getenv("CACHE_TTL", "3600"))  # segundos
_MAX = 500
_dados: OrderedDict = OrderedDict()
_trava = threading.Lock()


def chave(*partes) -> str:
    texto = " | ".join(str(p) for p in partes).lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w|]+", " ", texto).strip()


def obter(k: str):
    with _trava:
        item = _dados.get(k)
        if not item:
            return None
        valor, expira = item
        if time.monotonic() > expira:
            del _dados[k]
            return None
        _dados.move_to_end(k)
        return valor


def guardar(k: str, valor) -> None:
    with _trava:
        _dados[k] = (valor, time.monotonic() + _TTL)
        _dados.move_to_end(k)
        while len(_dados) > _MAX:
            _dados.popitem(last=False)


def limpar() -> None:
    with _trava:
        _dados.clear()


def tamanho() -> int:
    return len(_dados)
