"""Testes de integração — cascata de notificações + motor de tempos (Bloco B3).

Exigem Postgres real (RLS, FORCE ROW LEVEL SECURITY, índice único parcial de
`notificacoes_agendadas`). Rodar com `pytest -m integration`.

Cobre especificamente o que só é testável com banco: resolução de
destinatários (`Responsavel`), persistência de `leg_durations`/
`notificacoes_agendadas`, e — o pedido mais crítico do bloco — que cada
gatilho de cancelamento (desfazer checkin, ausente, reordenar) realmente
impede o envio de um `preparo` pendente, e que "estou atrasado" reagenda em
vez de cancelar.
"""
import datetime
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

import pytest

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
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from app.services.notificacoes import StubFCMSender
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _criar_cenario(
    session, n_paradas: int = 4, receber_notificacoes: bool = True,
    estimativas_por_ordem: dict[int, int] | None = None,
):
    """Tenant + 1 rota + N paradas/alunos/responsáveis + motorista/veículo,
    viagem já iniciada (trip_students em 'aguardando', ordem 1..N).
    `estimativas_por_ordem`: seta `Parada.duracao_estimada_segundos` por
    ordem — usado para controlar a previsão de trajeto sem precisar de
    amostras reais (não há `leg_durations` ainda numa viagem recém-criada)."""
    estimativas_por_ordem = estimativas_por_ordem or {}
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant B3 {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista B3", email=f"mot.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()
    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)

    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="B3T0001", km_atual=0)
    session.add(veiculo)

    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota B3", turno="manha", ativa=True)
    session.add(rota)
    session.flush()

    alunos_paradas = []
    responsaveis_por_aluno = {}
    for i in range(1, n_paradas + 1):
        parada = Parada(
            id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome=f"Parada {i}", ordem_base=i,
            geo=from_shape(Point(-46.6 + i * 0.001, -23.5 + i * 0.001), srid=4326),
            duracao_estimada_segundos=estimativas_por_ordem.get(i),
        )
        session.add(parada)
        session.flush()

        aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome=f"Aluno {i}", parada_id=parada.id, ativo=True)
        session.add(aluno)
        session.flush()

        resp_user = User(
            id=uuid.uuid4(), tenant_id=tenant.id, nome=f"Responsavel {i}", email=f"resp{i}.{uuid.uuid4()}@teste.com",
            senha_hash=hash_password("x"), role=UserRole.RESPONSAVEL, ativo=True,
        )
        session.add(resp_user)
        session.flush()

        responsavel = Responsavel(
            id=uuid.uuid4(), tenant_id=tenant.id, aluno_id=aluno.id, user_id=resp_user.id,
            permissoes={"receber_notificacoes": receber_notificacoes},
        )
        session.add(responsavel)

        alunos_paradas.append((aluno.id, parada.id, i))
        responsaveis_por_aluno[aluno.id] = responsavel

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.PLANEJADA,
    )
    session.add(viagem)
    session.flush()

    novos = tsm.iniciar_viagem(viagem, alunos_paradas, now=T0)
    session.add_all(novos)
    session.commit()

    trip_students = sorted(
        session.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id)), key=lambda ts: ts.ordem
    )
    return {
        "tenant_id": tenant.id, "viagem": viagem, "trip_students": trip_students,
        "responsaveis_por_aluno": responsaveis_por_aluno,
    }


def _preparo_pendente(session, trip_student_id):
    return session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == trip_student_id,
            NotificacaoAgendada.tipo == NotificacaoTipo.PREPARO,
            NotificacaoAgendada.estado == NotificacaoEstado.AGENDADO,
        )
    ).all()


# ---------------------------------------------------------------------------
# Imediatas — chegada/iminência
# ---------------------------------------------------------------------------


def test_cheguei_dispara_chegada_e_iminencia_imediatas(db_session):
    cenario = _criar_cenario(db_session, n_paradas=3)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo = ts_list[0]

    evento = tsm.registrar_cheguei(viagem, alvo, ts_list, now=_dt(300))
    db_session.add(evento)
    sender = StubFCMSender()
    pos_evento.processar_cheguei(db_session, viagem, ts_list, alvo, _dt(300), sender=sender)
    db_session.commit()

    resp_alvo = cenario["responsaveis_por_aluno"][alvo.aluno_id]
    resp_proximo = cenario["responsaveis_por_aluno"][ts_list[1].aluno_id]

    chegada = db_session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == alvo.id, NotificacaoAgendada.tipo == NotificacaoTipo.CHEGADA
        )
    ).one()
    assert chegada.estado == NotificacaoEstado.ENVIADO
    assert chegada.destinatario_user_id == resp_alvo.user_id

    iminencia = db_session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == ts_list[1].id, NotificacaoAgendada.tipo == NotificacaoTipo.IMINENCIA
        )
    ).one()
    assert iminencia.estado == NotificacaoEstado.ENVIADO
    assert iminencia.destinatario_user_id == resp_proximo.user_id

    assert len(sender.enviadas) == 2


def test_responsavel_sem_permissao_nao_recebe_notificacao(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2, receber_notificacoes=False)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo = ts_list[0]

    evento = tsm.registrar_cheguei(viagem, alvo, ts_list, now=_dt(100))
    db_session.add(evento)
    pos_evento.processar_cheguei(db_session, viagem, ts_list, alvo, _dt(100))
    db_session.commit()

    nenhuma = db_session.scalars(
        select(NotificacaoAgendada).where(NotificacaoAgendada.trip_student_id == alvo.id)
    ).all()
    assert nenhuma == []


# ---------------------------------------------------------------------------
# Preparo — agendado (não imediato), CLAUDE.md "faltam ~X min"
# ---------------------------------------------------------------------------


def test_checkin_agenda_preparo_com_trecho_curto_nao_inverte_com_iminencia(db_session):
    """Regressão explícita (CLAUDE.md §5): trecho curto até a PRÓXIMA parada
    (N+1) — 2,5min — não pode fazer o preparo de N+2 (trecho normal de
    10min depois) sair DEPOIS do ETA de N+1, quando "é a próxima" dispara.
    """
    cenario = _criar_cenario(db_session, n_paradas=3, estimativas_por_ordem={2: 150, 3: 600})
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1 = ts_list[0]

    ts1.estado = TripStudentEstado.CHEGOU
    ts1.chegou_em = _dt(100)
    evento = tsm.registrar_checkin(viagem, ts1, now=_dt(150))
    db_session.add(evento)
    pos_evento.processar_checkin(db_session, viagem, ts_list, ts1, _dt(150))
    db_session.commit()

    ts2, ts3 = ts_list[1], ts_list[2]
    eta_ts2 = _dt(150) + datetime.timedelta(seconds=150)  # ancora (150) + trecho até N+1 (150s)

    pendentes = _preparo_pendente(db_session, ts3.id)
    assert len(pendentes) == 1
    # sem o teto, o candidato seria eta_ts3 (_dt(900)) - 300s = _dt(600) —
    # bem DEPOIS do ETA de N+1 (_dt(300), quando "é a próxima" dispara).
    assert pendentes[0].agendado_para <= eta_ts2
    assert pendentes[0].agendado_para == eta_ts2  # teto ativo


def test_checkin_agenda_preparo_para_n_mais_2(db_session):
    cenario = _criar_cenario(db_session, n_paradas=4)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1 = ts_list[0]

    ts1.estado = TripStudentEstado.CHEGOU
    ts1.chegou_em = _dt(100)
    evento = tsm.registrar_checkin(viagem, ts1, now=_dt(150))
    db_session.add(evento)
    pos_evento.processar_checkin(db_session, viagem, ts_list, ts1, _dt(150))
    db_session.commit()

    alvo_n2 = ts_list[2]  # ordem 3 — 2º não-terminal após ordem 1
    pendentes = _preparo_pendente(db_session, alvo_n2.id)
    assert len(pendentes) == 1
    assert pendentes[0].agendado_para > _dt(150)
    assert pendentes[0].payload["faixa_min_baixo"] >= 0

    # ninguém mais tem preparo pendente
    for ts in ts_list:
        if ts.id != alvo_n2.id:
            assert _preparo_pendente(db_session, ts.id) == []


# ---------------------------------------------------------------------------
# CRÍTICO — cancelamento (CLAUDE.md §5)
# ---------------------------------------------------------------------------


def _preparar_checkin_com_preparo_pendente(session, n_paradas=4):
    cenario = _criar_cenario(session, n_paradas=n_paradas)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(session, cenario["tenant_id"])
    ts1 = ts_list[0]
    ts1.estado = TripStudentEstado.CHEGOU
    ts1.chegou_em = _dt(100)
    evento = tsm.registrar_checkin(viagem, ts1, now=_dt(150))
    session.add(evento)
    pos_evento.processar_checkin(session, viagem, ts_list, ts1, _dt(150))
    session.commit()
    return cenario


def test_desfazer_checkin_cancela_preparo_pendente(db_session):
    cenario = _preparar_checkin_com_preparo_pendente(db_session)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1 = ts_list[0]
    alvo_n2 = ts_list[2]
    assert len(_preparo_pendente(db_session, alvo_n2.id)) == 1

    evento = tsm.desfazer_checkin(viagem, ts1, now=_dt(160))
    db_session.add(evento)
    pos_evento.processar_desfazer_checkin(db_session, viagem, ts_list, ts1, _dt(160))
    db_session.commit()

    assert _preparo_pendente(db_session, alvo_n2.id) == []
    cancelada = db_session.scalars(
        select(NotificacaoAgendada).where(NotificacaoAgendada.trip_student_id == alvo_n2.id)
    ).one()
    assert cancelada.estado == NotificacaoEstado.CANCELADO
    assert "desfazer_checkin" in cancelada.motivo_cancelamento


def test_marcar_ausente_cancela_seu_proprio_preparo_pendente(db_session):
    cenario = _preparar_checkin_com_preparo_pendente(db_session)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo_n2 = ts_list[2]
    assert len(_preparo_pendente(db_session, alvo_n2.id)) == 1

    evento = tsm.registrar_ausente(viagem, alvo_n2, now=_dt(400))
    db_session.add(evento)
    pos_evento.processar_ausente(db_session, viagem, ts_list, alvo_n2, _dt(400))
    db_session.commit()

    assert _preparo_pendente(db_session, alvo_n2.id) == []
    cancelada = db_session.scalars(
        select(NotificacaoAgendada).where(NotificacaoAgendada.trip_student_id == alvo_n2.id)
    ).one()
    assert cancelada.estado == NotificacaoEstado.CANCELADO
    assert "ausente" in cancelada.motivo_cancelamento


def test_reordenar_cancela_preparo_do_trip_student_reordenado(db_session):
    cenario = _preparar_checkin_com_preparo_pendente(db_session)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo_n2 = ts_list[2]  # ordem 3, ainda 'aguardando' — pode ser reordenado
    assert alvo_n2.estado == TripStudentEstado.AGUARDANDO
    assert len(_preparo_pendente(db_session, alvo_n2.id)) == 1

    tsm.reordenar(viagem, [alvo_n2], {alvo_n2.id: 99})
    pos_evento.processar_reordenar(db_session, viagem, ts_list, [alvo_n2], _dt(200))
    db_session.commit()

    assert _preparo_pendente(db_session, alvo_n2.id) == []
    cancelada = db_session.scalars(
        select(NotificacaoAgendada).where(NotificacaoAgendada.trip_student_id == alvo_n2.id)
    ).one()
    assert cancelada.estado == NotificacaoEstado.CANCELADO
    assert "reordenad" in cancelada.motivo_cancelamento


def test_estou_atrasado_reagenda_em_vez_de_cancelar(db_session):
    cenario = _preparar_checkin_com_preparo_pendente(db_session)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo_n2 = ts_list[2]
    antes = _preparo_pendente(db_session, alvo_n2.id)
    assert len(antes) == 1
    agendado_para_antes = antes[0].agendado_para

    pos_evento.processar_estou_atrasado(db_session, viagem, ts_list, minutos=10, agora=_dt(200))
    db_session.commit()

    depois = _preparo_pendente(db_session, alvo_n2.id)
    assert len(depois) == 1  # reagendado — não cancelado, não duplicado
    assert depois[0].id == antes[0].id
    assert depois[0].agendado_para > agendado_para_antes
    assert viagem.atraso_manual_segundos == 600


# ---------------------------------------------------------------------------
# atraso_acumulado_segundos — diagnóstico, não entra na projeção
# ---------------------------------------------------------------------------


def test_atraso_acumulado_e_atraso_manual_sao_campos_independentes(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo = ts_list[0]

    evento = tsm.registrar_cheguei(viagem, alvo, ts_list, now=_dt(9999))  # bem atrasado vs. a semente
    db_session.add(evento)
    pos_evento.processar_cheguei(db_session, viagem, ts_list, alvo, _dt(9999))
    db_session.commit()

    assert viagem.atraso_acumulado_segundos > 0
    assert viagem.atraso_manual_segundos == 0  # nunca tocado pelo evento automático
