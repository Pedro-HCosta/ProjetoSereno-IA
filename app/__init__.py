"""Serviço de IA do Sereno.

Se alguém rodar um comando do projeto (ex.: python -m app.llm) num Python sem as dependências,
em vez de quebrar com ModuleNotFoundError, o projeto monta a .venv sozinho (iniciar.py) e
roda o MESMO comando dentro dela. Na Azure e na .venv as dependências já existem e nada disso roda.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

_DEPENDENCIAS = ("httpx", "fastapi", "jwt", "sklearn", "pandas", "faiss", "bs4", "dotenv")


def _garantir_dependencias() -> None:
    if all(importlib.util.find_spec(m) for m in _DEPENDENCIAS):
        return
    if os.environ.get("SERENO_AMBIENTE_PRONTO"):  # já estamos na .venv e mesmo assim falta algo: não entra em loop
        raise SystemExit("Faltam dependências mesmo dentro da .venv. Rode: python iniciar.py")

    raiz = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(raiz))
    import iniciar  # só biblioteca padrão

    iniciar.conferir_python()
    iniciar.preparar_venv()
    print(f"==> Rodando dentro do ambiente do projeto ({iniciar.VENV.name})", file=sys.stderr, flush=True)
    ambiente = dict(os.environ, SERENO_AMBIENTE_PRONTO="1")
    resultado = subprocess.run([str(iniciar.PY), *sys.orig_argv[1:]], cwd=os.getcwd(), env=ambiente)
    sys.exit(resultado.returncode)


_garantir_dependencias()
