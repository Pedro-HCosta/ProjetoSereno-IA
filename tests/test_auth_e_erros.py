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
