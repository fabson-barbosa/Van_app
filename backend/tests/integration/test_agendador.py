"""Testes de integração — processador do agendador (Bloco B3, CLAUDE.md §5).

Cobre os dois requisitos "CRÍTICO" do bloco:
1. Idempotência: reprocessar não duplica envio.
2. Corrida com cancelamento concorrente: `SELECT ... FOR UPDATE SKIP LOCKED`
   garante que uma notificação sendo cancelada bem na hora do processamento
   nunca é enviada — nem pelo worker que a puxou, nem depois.

Usa duas `Session`/conexões físicas SEPARADAS (não a fixture `db_session`
compartilhada) para simular de verdade duas transações concorrentes — é
exatamente o cenário de dois workers do agendador rodando ao mesmo tempo, ou
um worker rodando enquanto o motorista cancela pelo app.
"""
import datetime
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select, text

import pytest

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.aluno import Aluno, Responsavel
from app.models.motorista import Motorista
from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado, NotificacaoTipo
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.services.agendador import processar_notificacoes_pendentes
from app.services.notificacoes import StubFCMSender
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _criar_notificacao_pendente(session, agendado_para: datetime.datetime) -> dict:
    """Cadeia mínima de FKs + uma `NotificacaoAgendada` PREPARO em `agendado`."""
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Agendador {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista", email=f"m.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()
    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)
    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="AGD0001", km_atual=0)
    session.add(veiculo)
    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota Agendador", turno="manha", ativa=True)
    session.add(rota)
    session.flush()
    parada = Parada(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome="Parada", ordem_base=1,
        geo=from_shape(Point(-46.6, -23.5), srid=4326),
    )
    session.add(parada)
    session.flush()
    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome="Aluno", parada_id=parada.id, ativo=True)
    session.add(aluno)
    session.flush()
    resp_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Responsavel", email=f"r.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.RESPONSAVEL, ativo=True,
    )
    session.add(resp_user)
    session.flush()
    responsavel = Responsavel(
        id=uuid.uuid4(), tenant_id=tenant.id, aluno_id=aluno.id, user_id=resp_user.id,
        permissoes={"receber_notificacoes": True},
    )
    session.add(responsavel)

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.EM_ANDAMENTO, iniciada_em=T0,
    )
    session.add(viagem)
    session.flush()
    trip_student = TripStudent(
        id=uuid.uuid4(), tenant_id=tenant.id, viagem_id=viagem.id, aluno_id=aluno.id, parada_id=parada.id,
        ordem=1, estado=TripStudentEstado.AGUARDANDO,
    )
    session.add(trip_student)
    session.flush()

    notificacao = NotificacaoAgendada(
        id=uuid.uuid4(), tenant_id=tenant.id, viagem_id=viagem.id, trip_student_id=trip_student.id,
        destinatario_user_id=resp_user.id, tipo=NotificacaoTipo.PREPARO, estado=NotificacaoEstado.AGENDADO,
        agendado_para=agendado_para, payload={"faixa_min_baixo": 5, "faixa_min_alto": 10},
    )
    session.add(notificacao)
    session.commit()

    return {"tenant_id": tenant.id, "notificacao_id": notificacao.id, "destinatario_user_id": resp_user.id}


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------


def test_reprocessar_nao_duplica_envio(db_session):
    cenario = _criar_notificacao_pendente(db_session, agendado_para=_dt(-60))
    set_tenant(db_session, cenario["tenant_id"])
    sender = StubFCMSender()

    primeira_passada = processar_notificacoes_pendentes(db_session, _dt(0), sender)
    segunda_passada = processar_notificacoes_pendentes(db_session, _dt(0), sender)

    assert primeira_passada == 1
    assert segunda_passada == 0
    assert len(sender.enviadas) == 1  # não duplicou

    notificacao = db_session.get(NotificacaoAgendada, cenario["notificacao_id"])
    assert notificacao.estado == NotificacaoEstado.ENVIADO


# ---------------------------------------------------------------------------
# CRÍTICO — corrida com cancelamento concorrente
# ---------------------------------------------------------------------------


def test_cancelamento_concorrente_ao_processamento_nao_envia(db_session):
    """Simula: motorista cancela (desfazer checkin) BEM na hora em que o
    worker do agendador ia processar a mesma linha. `FOR UPDATE SKIP LOCKED`
    garante que o worker pula a linha travada em vez de esperar/enviar."""
    cenario = _criar_notificacao_pendente(db_session, agendado_para=_dt(-60))
    tenant_id = cenario["tenant_id"]

    sessao_cancelamento = SessionLocal()
    sessao_worker = SessionLocal()
    try:
        set_tenant(sessao_cancelamento, tenant_id)
        set_tenant(sessao_worker, tenant_id)

        # 1) "motorista" abre a transação de cancelamento e TRAVA a linha,
        #    mas ainda não comitou — como se estivesse no meio do request.
        notificacao_cancelando = sessao_cancelamento.execute(
            select(NotificacaoAgendada)
            .where(NotificacaoAgendada.id == cenario["notificacao_id"])
            .with_for_update()
        ).scalar_one()
        notificacao_cancelando.estado = NotificacaoEstado.CANCELADO
        notificacao_cancelando.motivo_cancelamento = "desfazer_checkin (teste de corrida)"
        sessao_cancelamento.flush()  # UPDATE já foi pro banco, mas a transação segue aberta (sem commit)

        # 2) worker do agendador roda NO MEIO da transação de cancelamento —
        #    a linha está travada, `SKIP LOCKED` faz o worker pular ela.
        sender = StubFCMSender()
        enviadas_durante_a_corrida = processar_notificacoes_pendentes(sessao_worker, _dt(0), sender)
        assert enviadas_durante_a_corrida == 0
        assert sender.enviadas == []

        # 3) cancelamento finalmente comita.
        sessao_cancelamento.commit()

        # 4) worker roda de novo — a linha já está 'cancelado', continua não sendo enviada.
        enviadas_depois = processar_notificacoes_pendentes(sessao_worker, _dt(0), sender)
        assert enviadas_depois == 0
        assert sender.enviadas == []
    finally:
        sessao_cancelamento.close()
        sessao_worker.close()

    verificacao = SessionLocal()
    try:
        set_tenant(verificacao, tenant_id)
        notificacao_final = verificacao.get(NotificacaoAgendada, cenario["notificacao_id"])
        assert notificacao_final.estado == NotificacaoEstado.CANCELADO
        assert notificacao_final.enviado_em is None
    finally:
        verificacao.close()
