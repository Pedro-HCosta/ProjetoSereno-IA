"""Um comando só para rodar o serviço de IA, em qualquer sistema.

    python iniciar.py              cria a .venv (se preciso), instala, prepara e sobe o serviço
    python iniciar.py testes       roda os testes automatizados
    python iniciar.py avaliar      avaliação do RAG com o LLM (gera rag/avaliacao/respostas_llm.md)
    python iniciar.py diagnostico  testa a conexão com o LLM
    python iniciar.py treinar      gera os dados, treina o modelo e refaz o índice das leis
    python iniciar.py --rede       sobe o serviço acessível na rede (para testar do celular/emulador)

Não precisa ativar a .venv: o script usa o Python dela diretamente.
Só usa a biblioteca padrão, então roda antes de qualquer instalação.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
VENV = RAIZ / ".venv"
PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
REQUISITOS = RAIZ / "requirements-dev.txt"
MARCA = VENV / ".requisitos-instalados"

COMANDOS = {"servidor", "testes", "avaliar", "diagnostico", "treinar"}


def passo(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def rodar(*args: str) -> None:
    resultado = subprocess.run([str(PY), *args], cwd=RAIZ)
    if resultado.returncode != 0:
        sys.exit(resultado.returncode)


def conferir_python() -> None:
    if sys.version_info < (3, 12):
        sys.exit(f"Precisa do Python 3.12 ou mais novo (você está com {sys.version.split()[0]}). "
                 "Baixe em python.org e rode de novo.")


def preparar_venv() -> None:
    if not PY.exists():
        passo("Criando o ambiente virtual (.venv) — só na primeira vez")
        venv.create(VENV, with_pip=True)
    # Reinstala só quando os requirements mudarem
    assinatura = hashlib.sha256((RAIZ / "requirements.txt").read_bytes() + REQUISITOS.read_bytes()).hexdigest()
    if not MARCA.exists() or MARCA.read_text() != assinatura:
        passo("Instalando as dependências (pode levar alguns minutos na primeira vez)")
        rodar("-m", "pip", "install", "--upgrade", "pip", "-q")
        rodar("-m", "pip", "install", "-r", str(REQUISITOS), "-q")
        MARCA.write_text(assinatura)


def preparar_env() -> None:
    env = RAIZ / ".env"
    if not env.exists():
        shutil.copy(RAIZ / ".env.example", env)
        passo("Criei o arquivo .env a partir do .env.example")
        print("    Abra o .env e preencha JWT_SECRET e AI_API_KEY.")
        print("    Sem a chave do LLM o serviço funciona, mas responde com o texto alternativo.")


def preparar_artefatos(forcar: bool = False) -> None:
    if forcar or not (RAIZ / "ml" / "dados" / "avaliacoes_sinteticas.csv").exists():
        passo("Gerando os dados sintéticos")
        rodar("-m", "ml.gerar_dados")
    if forcar or not (RAIZ / "ml" / "modelo" / "modelo_previsao.joblib").exists():
        passo("Treinando o modelo de previsão")
        rodar("-m", "ml.treinar")
    if forcar or not (RAIZ / "rag" / "indice" / "leis.faiss").exists():
        passo("Montando o índice das leis")
        rodar("-m", "rag.indexar")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    comando = args[0] if args else "servidor"
    host = "0.0.0.0" if "--rede" in sys.argv else "127.0.0.1"
    if comando not in COMANDOS:
        sys.exit(__doc__)

    conferir_python()
    preparar_venv()
    preparar_env()
    preparar_artefatos(forcar=comando == "treinar")

    if comando == "testes":
        rodar("-m", "pytest", "-q")
    elif comando == "avaliar":
        rodar("-m", "rag.avaliar", "--com-llm")
    elif comando == "diagnostico":
        rodar("-m", "app.llm")
    elif comando == "servidor":
        porta = os.getenv("PORT", "8000")
        passo(f"Serviço no ar: http://localhost:{porta}/ia/docs  (Ctrl+C para parar)")
        if host == "0.0.0.0":
            print(f"    Na rede: http://<IP deste PC>:{porta}  (emulador Android: http://10.0.2.2:{porta})")
        try:
            subprocess.run([str(PY), "-m", "uvicorn", "app.main:app", "--host", host, "--port", porta], cwd=RAIZ)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
