"""Testes de integração — `TwilioWhatsAppSender` (piloto WhatsApp, ver
PROGRESSO.md).

Precisa de Postgres real (consulta `Responsavel`/`Aluno` com RLS). A chamada
HTTP para a Twilio em si é substituída por um cliente fake — o que se testa
aqui é a lógica de resolução de telefone, montagem de texto e tratamento de
falha (rede, número rejeitado pela Twilio), nunca a rede de verdade.
"""
import uuid

import httpx
import pytest

from app.core.security import hash_password
from app.models.aluno import Aluno, CanalNotificacao, Responsavel
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.whatsapp_twilio import TwilioWhatsAppSender
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

_CREDENCIAIS = dict(account_sid="ACfake", auth_token="tokenfake", whatsapp_from="+14155238886")


class _RespostaFake:
    def __init__(self, status_code: int = 201) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("erro", request=None, response=self)


class _ClienteFake:
    def __init__(self, *, levantar: Exception | None = None, status_code: int = 201) -> None:
        self.chamadas: list[dict] = []
        self._levantar = levantar
        self._status_code = status_code

    def post(self, url: str, *, data: dict, auth: tuple[str, str]) -> _RespostaFake:
        if self._levantar is not None:
            raise self._levantar
        self.chamadas.append(data)
        return _RespostaFake(self._status_code)


def _criar_tenant_user_aluno_responsavel(session, *, telefone: str | None = "+5516999998888") -> dict:
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant WA {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    resp_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Mãe do Aluno", email=f"resp.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.RESPONSAVEL, ativo=True,
    )
    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome="Joãozinho", ativo=True)
    session.add_all([resp_user, aluno])
    session.flush()

    responsavel = Responsavel(
        tenant_id=tenant.id, aluno_id=aluno.id, user_id=resp_user.id,
        telefone=telefone, canal_notificacao=CanalNotificacao.WHATSAPP,
    )
    session.add(responsavel)
    session.commit()
    return {"tenant_id": tenant.id, "user_id": resp_user.id, "aluno_id": aluno.id}


def _payload(aluno_id: uuid.UUID, **extra) -> dict:
    return {"aluno_id": str(aluno_id), **extra}


def test_sucesso_envia_texto_com_nome_do_aluno_e_faixa(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session)
    cliente = _ClienteFake()

    TwilioWhatsAppSender(db_session, cliente=cliente, **_CREDENCIAIS).enviar(
        destinatario_user_id=ids["user_id"], tipo="preparo",
        payload=_payload(ids["aluno_id"], faixa_min_baixo=5, faixa_min_alto=10),
    )

    assert len(cliente.chamadas) == 1
    corpo = cliente.chamadas[0]
    assert "Joãozinho" in corpo["Body"]
    assert "5" in corpo["Body"] and "10" in corpo["Body"]
    assert corpo["To"] == "whatsapp:+5516999998888"
    assert corpo["From"] == "whatsapp:+14155238886"


def test_falha_de_rede_nao_lanca_excecao(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session)
    cliente = _ClienteFake(levantar=httpx.ConnectError("timeout"))

    # Não deve lançar — mesmo contrato de "nunca falha" dos outros senders.
    TwilioWhatsAppSender(db_session, cliente=cliente, **_CREDENCIAIS).enviar(
        destinatario_user_id=ids["user_id"], tipo="chegada", payload=_payload(ids["aluno_id"]),
    )


def test_numero_rejeitado_pela_twilio_nao_lanca_excecao(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session, telefone="+5516000000000")
    cliente = _ClienteFake(status_code=400)  # Twilio: "To" number inválido

    TwilioWhatsAppSender(db_session, cliente=cliente, **_CREDENCIAIS).enviar(
        destinatario_user_id=ids["user_id"], tipo="iminencia", payload=_payload(ids["aluno_id"]),
    )


def test_sem_telefone_cadastrado_nao_faz_chamada(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session, telefone=None)
    cliente = _ClienteFake()

    TwilioWhatsAppSender(db_session, cliente=cliente, **_CREDENCIAIS).enviar(
        destinatario_user_id=ids["user_id"], tipo="chegada", payload=_payload(ids["aluno_id"]),
    )

    assert cliente.chamadas == []


def test_sem_credenciais_configuradas_nao_faz_chamada(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session)
    cliente = _ClienteFake()

    TwilioWhatsAppSender(
        db_session, cliente=cliente, account_sid=None, auth_token=None, whatsapp_from=None
    ).enviar(destinatario_user_id=ids["user_id"], tipo="chegada", payload=_payload(ids["aluno_id"]))

    assert cliente.chamadas == []


def test_tipo_sem_redacao_no_whatsapp_nao_faz_chamada(db_session):
    ids = _criar_tenant_user_aluno_responsavel(db_session)
    cliente = _ClienteFake()

    TwilioWhatsAppSender(db_session, cliente=cliente, **_CREDENCIAIS).enviar(
        destinatario_user_id=ids["user_id"], tipo="dismiss_chegada", payload={"trip_student_id": "ts1"},
    )

    assert cliente.chamadas == []
