import time
from pathlib import Path

import jwt
import pytest

SEGREDO = "segredo-de-teste-com-pelo-menos-32-caracteres!!"
RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET", SEGREDO)
    monkeypatch.setenv("AI_API_KEY", "")  # nenhum teste chama um LLM de verdade
    monkeypatch.setenv("JAVA_API_URL", "")
    yield


def token(segredo=SEGREDO, iss="sereno-auth", aud="sereno-app", expira_em=3600, sub="1", role="CIDADAO"):
    agora = int(time.time())
    return jwt.encode(
        {"sub": sub, "email": "cidadao@sereno.app", "role": role, "iss": iss, "aud": aud, "iat": agora, "exp": agora + expira_em},
        segredo,
        algorithm="HS256",
    )


@pytest.fixture
def cabecalho():
    return {"Authorization": f"Bearer {token()}"}


@pytest.fixture
def cliente():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
