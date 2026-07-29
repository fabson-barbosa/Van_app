"""Testes de integração — `ExpoPushSender` (Bloco B5).

Precisa de Postgres real (consulta/atualiza `device_tokens` com RLS). O HTTP
para o Expo Push Service em si é substituído por um cliente fake (nunca sai
da rede em teste) — o que se testa aqui é a lógica de seleção de tokens,
montagem de mensagem e desativação de token morto, não a rede.
"""
import uuid

from sqlalchemy import select

import pytest

from app.core.security import hash_password
from app.models.device_token import DeviceToken
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.expo_push import ExpoPushSender
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration


class _RespostaFake:
    def __init__(self, corpo: dict) -> None:
        self._corpo = corpo

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._corpo


class _ClienteFake:
    """Substitui `httpx.Client` — grava as chamadas, devolve uma resposta
    programada (uma entrada `data[]` por mensagem enviada, na mesma ordem)."""

    def __init__(self, resultados_por_token: dict[str, dict] | None = None) -> None:
        self.chamadas: list[list[dict]] = []
        self._resultados_por_token = resultados_por_token or {}

    def post(self, url: str, *, json: list[dict], headers: dict) -> _RespostaFake:
        self.chamadas.append(json)
        dados = [self._resultados_por_token.get(m["to"], {"status": "ok", "id": "fake-id"}) for m in json]
        return _RespostaFake({"data": dados})


def _criar_tenant_e_user(session) -> tuple[uuid.UUID, uuid.UUID]:
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant ExpoPush {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Responsável ExpoPush", email=f"resp.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.RESPONSAVEL, ativo=True,
    )
    session.add(user)
    session.commit()
    return tenant.id, user.id


def test_sem_token_ativo_nao_faz_chamada_http(db_session):
    _tenant_id, user_id = _criar_tenant_e_user(db_session)
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})

    assert cliente.chamadas == []


def test_token_ativo_recebe_mensagem_com_data_e_titulo_fallback(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[abc]", ativo=True))
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(
        destinatario_user_id=user_id, tipo="chegada",
        payload={"viagem_id": "v1", "trip_student_id": "ts1", "aluno_id": "a1"},
    )

    assert len(cliente.chamadas) == 1
    (mensagem,) = cliente.chamadas[0]
    assert mensagem["to"] == "ExponentPushToken[abc]"
    assert mensagem["title"] == "Chegamos!"
    assert mensagem["data"]["tipo"] == "chegada"
    assert mensagem["data"]["trip_student_id"] == "ts1"


def test_token_inativo_nao_recebe_mensagem(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(
        DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[morto]", ativo=False)
    )
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})

    assert cliente.chamadas == []


def test_dismiss_chegada_e_silencioso_sem_titulo_nem_corpo(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    # Token PRÓPRIO, não o "[abc]" de
    # `test_token_ativo_recebe_mensagem_com_data_e_titulo_fallback`:
    # `uq_device_tokens_token` é global, não por tenant (um aparelho tem um
    # token só — ver models/device_token.py), e o fixture `db_session` só faz
    # rollback, que não desfaz o commit do teste anterior. Tenants diferentes
    # não salvam: a colisão é no literal. Mesmo motivo pelo qual
    # `_criar_tenant_e_user` já gera nome de tenant e e-mail com uuid.
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[dismiss]", ativo=True))
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(
        destinatario_user_id=user_id, tipo="dismiss_chegada", payload={"trip_student_id": "ts1"}
    )

    (mensagem,) = cliente.chamadas[0]
    assert "title" not in mensagem
    assert "body" not in mensagem
    assert mensagem["data"]["tipo"] == "dismiss_chegada"


def test_device_not_registered_desativa_o_token(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    token = DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[morto2]", ativo=True)
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    cliente = _ClienteFake({
        "ExponentPushToken[morto2]": {"status": "error", "message": "não registrado", "details": {"error": "DeviceNotRegistered"}}
    })
    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})
    db_session.commit()

    atualizado = db_session.get(DeviceToken, token_id)
    assert atualizado.ativo is False
    assert atualizado.desativado_em is not None


def test_erro_diferente_de_device_not_registered_nao_desativa_o_token(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    token = DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[temp]", ativo=True)
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    cliente = _ClienteFake({
        "ExponentPushToken[temp]": {"status": "error", "message": "rate limited", "details": {"error": "MessageRateExceeded"}}
    })
    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})
    db_session.commit()

    atualizado = db_session.get(DeviceToken, token_id)
    assert atualizado.ativo is True


def test_multiplos_tokens_do_mesmo_usuario_recebem_todos(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[celular]", ativo=True))
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token="ExponentPushToken[tablet]", ativo=True))
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="iminencia", payload={})

    (mensagens,) = cliente.chamadas
    tokens_enviados = {m["to"] for m in mensagens}
    assert tokens_enviados == {"ExponentPushToken[celular]", "ExponentPushToken[tablet]"}
