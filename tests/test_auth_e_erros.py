"""JWT do Contrato e formato de erro padrão."""
from tests.conftest import token

CORPO = {"localId": 1, "diaSemana": 1, "hora": 8}


def test_health_e_publico(cliente):
    r = cliente.get("/ia/health")
    assert r.status_code == 200
    assert r.json()["componentes"]["modelo_previsao"] == "UP"


def test_sem_token_responde_401_no_formato_padrao(cliente):
    r = cliente.post("/ia/previsao-calma", json=CORPO)
    assert r.status_code == 401
    corpo = r.json()
    assert set(corpo) == {"status", "erro", "mensagem", "campos", "timestamp", "path"}
    assert corpo["erro"] == "NAO_AUTENTICADO"
    assert corpo["path"] == "/ia/previsao-calma"


def test_token_expirado_responde_401(cliente):
    r = cliente.post("/ia/previsao-calma", json=CORPO, headers={"Authorization": f"Bearer {token(expira_em=-10)}"})
    assert r.status_code == 401
    assert "expirada" in r.json()["mensagem"]


def test_token_com_outro_segredo_responde_401(cliente):
    falso = token(segredo="outro-segredo-qualquer-com-32-caracteres-ou-mais")
    assert cliente.post("/ia/previsao-calma", json=CORPO, headers={"Authorization": f"Bearer {falso}"}).status_code == 401


def test_token_de_outro_emissor_responde_401(cliente):
    r = cliente.post("/ia/previsao-calma", json=CORPO, headers={"Authorization": f"Bearer {token(iss='outro')}"})
    assert r.status_code == 401


def test_token_valido_da_api_java_e_aceito(cliente, cabecalho):
    assert cliente.post("/ia/previsao-calma", json=CORPO, headers=cabecalho).status_code == 200


def test_validacao_responde_400_com_campo(cliente, cabecalho):
    r = cliente.post("/ia/previsao-calma", json={"localId": 1, "diaSemana": 9, "hora": 30}, headers=cabecalho)
    assert r.status_code == 400
    corpo = r.json()
    assert corpo["erro"] == "VALIDACAO"
    assert {c["campo"] for c in corpo["campos"]} == {"diaSemana", "hora"}


def test_segredo_em_base64_quando_configurado(cliente, monkeypatch):
    """Java com Decoders.BASE64: a chave são os bytes decodificados, não o texto."""
    import base64
    import os

    bytes_chave = os.urandom(32)
    monkeypatch.setenv("JWT_SECRET", base64.b64encode(bytes_chave).decode())
    monkeypatch.setenv("JWT_SECRET_BASE64", "true")
    corpo = {"situacao": "O elevador da estação está parado. Quais são meus direitos?"}
    ok = cliente.post("/ia/direitos", json=corpo, headers={"Authorization": f"Bearer {token(segredo=bytes_chave)}"})
    assert ok.status_code == 200
    texto = cliente.post("/ia/direitos", json=corpo, headers={"Authorization": f"Bearer {token()}"})
    assert texto.status_code == 401
