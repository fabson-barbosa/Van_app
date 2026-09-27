"""Testes de integração — `ExpoPushSender` (Bloco B5).

Precisa de Postgres real (consulta/atualiza `device_tokens` com RLS). O HTTP
para o Expo Push Service em si é substituído por um cliente fake (nunca sai
da rede em teste) — o que se testa aqui é a lógica de seleção de tokens,
montagem de mensagem e desativação de token morto, não a rede.
"""
import uuid

import httpx
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


def _token(apelido: str) -> str:
    """`uq_device_tokens_token` é único GLOBAL, não por tenant (um token do Expo
    identifica um aparelho físico, e o mesmo token em dois tenants tem que
    virar 409 — ver `models/device_token.py` e `app/api/dispositivos.py`), então
    usar tenants diferentes não salva: a colisão é no literal. E o fixture
    `db_session` só faz rollback, que não desfaz o commit do teste anterior —
    literal fixo colide entre dois testes da MESMA rodada e entre rodadas
    sucessivas. O sufixo aleatório mantém o apelido legível na asserção sem
    depender de base limpa (mesmo motivo pelo qual `_criar_tenant_e_user` já
    gera nome de tenant e e-mail com uuid)."""
    return f"ExponentPushToken[{apelido}-{uuid.uuid4().hex[:8]}]"


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
    token = _token("abc")
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=token, ativo=True))
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(
        destinatario_user_id=user_id, tipo="chegada",
        payload={"viagem_id": "v1", "trip_student_id": "ts1", "aluno_id": "a1"},
    )

    assert len(cliente.chamadas) == 1
    (mensagem,) = cliente.chamadas[0]
    assert mensagem["to"] == token
    assert mensagem["title"] == "Chegamos!"
    assert mensagem["data"]["tipo"] == "chegada"
    assert mensagem["data"]["trip_student_id"] == "ts1"


def test_token_inativo_nao_recebe_mensagem(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(
        DeviceToken(tenant_id=tenant_id, user_id=user_id, token=_token("inativo"), ativo=False)
    )
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})

    assert cliente.chamadas == []


def test_dismiss_chegada_e_silencioso_sem_titulo_nem_corpo(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=_token("silencioso"), ativo=True))
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
    valor = _token("morto")
    token = DeviceToken(tenant_id=tenant_id, user_id=user_id, token=valor, ativo=True)
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    cliente = _ClienteFake({
        valor: {"status": "error", "message": "não registrado", "details": {"error": "DeviceNotRegistered"}}
    })
    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})
    db_session.commit()

    atualizado = db_session.get(DeviceToken, token_id)
    assert atualizado.ativo is False
    assert atualizado.desativado_em is not None


def test_erro_diferente_de_device_not_registered_nao_desativa_o_token(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    valor = _token("rate-limited")
    token = DeviceToken(tenant_id=tenant_id, user_id=user_id, token=valor, ativo=True)
    db_session.add(token)
    db_session.commit()
    token_id = token.id

    cliente = _ClienteFake({
        valor: {"status": "error", "message": "rate limited", "details": {"error": "MessageRateExceeded"}}
    })
    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="chegada", payload={})
    db_session.commit()

    atualizado = db_session.get(DeviceToken, token_id)
    assert atualizado.ativo is True


def test_resposta_nao_json_nao_derruba_a_transacao_do_evento(db_session):
    """Contrato "nunca lança" (docstring do módulo): `ExpoPushSender` roda
    ANTES do commit do evento de domínio. Um proxy/captive portal devolvendo
    HTML com status 200 faz `.json()` levantar — se isso vazar, o Cheguei do
    motorista é perdido por causa de uma falha de push."""
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=_token("corpo-invalido"), ativo=True))
    db_session.commit()

    class _RespostaHtml:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

    class _ClienteHtml:
        def post(self, url: str, *, json: list[dict], headers: dict) -> _RespostaHtml:
            return _RespostaHtml()

    ExpoPushSender(db_session, cliente=_ClienteHtml()).enviar(
        destinatario_user_id=user_id, tipo="chegada", payload={}
    )  # não pode levantar


def test_falha_de_rede_nao_derruba_a_transacao_do_evento(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=_token("sem-rede"), ativo=True))
    db_session.commit()

    class _ClienteOffline:
        def post(self, url: str, *, json: list[dict], headers: dict):
            raise httpx.ConnectError("sem rota para o host")

    ExpoPushSender(db_session, cliente=_ClienteOffline()).enviar(
        destinatario_user_id=user_id, tipo="chegada", payload={}
    )  # não pode levantar


def test_multiplos_tokens_do_mesmo_usuario_recebem_todos(db_session):
    tenant_id, user_id = _criar_tenant_e_user(db_session)
    celular, tablet = _token("celular"), _token("tablet")
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=celular, ativo=True))
    db_session.add(DeviceToken(tenant_id=tenant_id, user_id=user_id, token=tablet, ativo=True))
    db_session.commit()
    cliente = _ClienteFake()

    ExpoPushSender(db_session, cliente=cliente).enviar(destinatario_user_id=user_id, tipo="iminencia", payload={})

    (mensagens,) = cliente.chamadas
    tokens_enviados = {m["to"] for m in mensagens}
    assert tokens_enviados == {celular, tablet}
