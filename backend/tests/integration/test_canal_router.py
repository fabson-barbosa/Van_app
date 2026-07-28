"""Testes de integração — `ChannelRouterSender` (seleção de canal por
responsável, piloto WhatsApp via Twilio — ver PROGRESSO.md).

Precisa de Postgres real (consulta `Responsavel` com RLS). Os dois
sub-senders (push/whatsapp) são fakes em memória — o que se testa aqui é só
o roteamento por `canal_notificacao`, não a entrega de verdade (já coberta
por `test_expo_push.py`/`test_whatsapp_twilio.py`).
"""
import uuid

import httpx
import pytest

from app.core.security import hash_password
from app.models.aluno import Aluno, CanalNotificacao, Responsavel
from app.models.tenant import Tenant
from app.models.user import User, UserRole
from app.services.canal_router import ChannelRouterSender
from app.services.whatsapp_twilio import TwilioWhatsAppSender
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration


class _SenderFake:
    def __init__(self) -> None:
        self.chamadas: list[dict] = []

    def enviar(self, *, destinatario_user_id, tipo, payload) -> None:
        self.chamadas.append({"destinatario_user_id": destinatario_user_id, "tipo": tipo, "payload": payload})


class _ClienteHttpQueBrigaComARede:
    """Substitui `httpx.Client` dentro do `TwilioWhatsAppSender` — toda
    chamada estoura, como uma falha real de rede/DNS/timeout contra a API da
    Twilio."""

    def post(self, *args, **kwargs):
        raise httpx.ConnectError("rede fora do ar")


def _criar_responsavel(session, tenant_id, *, canal: CanalNotificacao, aluno_nome="Aluno") -> dict:
    resp_user = User(
        id=uuid.uuid4(), tenant_id=tenant_id, nome="Responsável", email=f"resp.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.RESPONSAVEL, ativo=True,
    )
    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant_id, nome=aluno_nome, ativo=True)
    session.add_all([resp_user, aluno])
    session.flush()
    responsavel = Responsavel(
        tenant_id=tenant_id, aluno_id=aluno.id, user_id=resp_user.id,
        telefone="+5516999998888", canal_notificacao=canal,
    )
    session.add(responsavel)
    session.commit()
    return {"user_id": resp_user.id, "aluno_id": aluno.id}


@pytest.fixture()
def tenant_id(db_session):
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Router {uuid.uuid4()}", plano="pro", status_billing="ativo")
    db_session.add(tenant)
    db_session.commit()
    set_tenant(db_session, tenant.id)
    return tenant.id


def test_canal_push_only_nao_chama_whatsapp(db_session, tenant_id):
    ids = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.PUSH)
    push, whatsapp = _SenderFake(), _SenderFake()
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp)

    router.enviar(destinatario_user_id=ids["user_id"], tipo="chegada", payload={"aluno_id": str(ids["aluno_id"])})

    assert len(push.chamadas) == 1
    assert whatsapp.chamadas == []


def test_canal_whatsapp_only_nao_chama_push(db_session, tenant_id):
    ids = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.WHATSAPP)
    push, whatsapp = _SenderFake(), _SenderFake()
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp)

    router.enviar(destinatario_user_id=ids["user_id"], tipo="preparo", payload={"aluno_id": str(ids["aluno_id"])})

    assert push.chamadas == []
    assert len(whatsapp.chamadas) == 1


def test_canal_ambos_chama_os_dois(db_session, tenant_id):
    ids = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.AMBOS)
    push, whatsapp = _SenderFake(), _SenderFake()
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp)

    router.enviar(destinatario_user_id=ids["user_id"], tipo="iminencia", payload={"aluno_id": str(ids["aluno_id"])})

    assert len(push.chamadas) == 1
    assert len(whatsapp.chamadas) == 1


def test_responsavel_nao_encontrado_cai_no_push_por_padrao(db_session, tenant_id):
    push, whatsapp = _SenderFake(), _SenderFake()
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp)

    # aluno_id que não corresponde a nenhum Responsavel cadastrado.
    router.enviar(destinatario_user_id=uuid.uuid4(), tipo="chegada", payload={"aluno_id": str(uuid.uuid4())})

    assert len(push.chamadas) == 1
    assert whatsapp.chamadas == []


def test_dismiss_chegada_vai_sempre_so_para_push_mesmo_com_canal_whatsapp(db_session, tenant_id):
    ids = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.WHATSAPP)
    push, whatsapp = _SenderFake(), _SenderFake()
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp)

    router.enviar(destinatario_user_id=ids["user_id"], tipo="dismiss_chegada", payload={"trip_student_id": "ts1"})

    assert len(push.chamadas) == 1
    assert whatsapp.chamadas == []


def test_falha_de_um_destinatario_nao_impede_envio_aos_outros(db_session, tenant_id):
    """`AMBOS`: a perna do WhatsApp falha de verdade (rede fora, via
    `TwilioWhatsAppSender` real com um cliente HTTP que estoura) — nem o push
    do MESMO destinatário, nem o envio a um segundo destinatário são afetados.
    A garantia vem do contrato "nunca lança" de cada sender (mesmo padrão do
    `ExpoPushSender`), não de um try/except no router."""
    ids1 = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.AMBOS, aluno_nome="Aluno 1")
    ids2 = _criar_responsavel(db_session, tenant_id, canal=CanalNotificacao.PUSH, aluno_nome="Aluno 2")
    push = _SenderFake()
    whatsapp_com_falha = TwilioWhatsAppSender(
        db_session, cliente=_ClienteHttpQueBrigaComARede(),
        account_sid="ACfake", auth_token="tokenfake", whatsapp_from="+14155238886",
    )
    router = ChannelRouterSender(db_session, push_sender=push, whatsapp_sender=whatsapp_com_falha)

    router.enviar(destinatario_user_id=ids1["user_id"], tipo="chegada", payload={"aluno_id": str(ids1["aluno_id"])})
    router.enviar(destinatario_user_id=ids2["user_id"], tipo="chegada", payload={"aluno_id": str(ids2["aluno_id"])})

    assert len(push.chamadas) == 2
