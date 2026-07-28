"""Testes de integração — Bloco B5: payload roteável e sinal de dismiss.

Reusa o cenário de `test_notificacoes_agendamento.py` (Postgres real —
`Responsavel`/`NotificacaoAgendada` persistidos). Cobre dois pontos novos do
B5 que não existiam no B3:

1. Todo payload de push (imediato ou agendado) carrega `viagem_id`/
   `trip_student_id`/`aluno_id` — é o que o app Responsável usa pra abrir a
   tela do filho certo ao tocar na notificação.
2. `dismiss_chegada` (sinal silencioso, nunca persistido em
   `notificacoes_agendadas`) dispara em Checkin sempre, e em Ausente só
   quando o aluno passou por `chegou` antes (`chegou_em is not None`).
"""
import datetime

from sqlalchemy import select

import pytest

from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado, NotificacaoTipo
from app.models.trip_student import TripStudentEstado
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from app.services.notificacoes import StubFCMSender
from tests.integration.conftest import set_tenant
from tests.integration.test_notificacoes_agendamento import _criar_cenario

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def test_payload_de_chegada_e_iminencia_inclui_ids_de_roteamento(db_session):
    cenario = _criar_cenario(db_session, n_paradas=3)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    alvo, proximo = ts_list[0], ts_list[1]

    evento = tsm.registrar_cheguei(viagem, alvo, ts_list, ocorrido_em=_dt(100), registrado_em=_dt(100))
    db_session.add(evento)
    pos_evento.processar_cheguei(db_session, viagem, ts_list, alvo, _dt(100), sender=StubFCMSender())
    db_session.commit()

    chegada = db_session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == alvo.id, NotificacaoAgendada.tipo == NotificacaoTipo.CHEGADA
        )
    ).one()
    assert chegada.payload["viagem_id"] == str(viagem.id)
    assert chegada.payload["trip_student_id"] == str(alvo.id)
    assert chegada.payload["aluno_id"] == str(alvo.aluno_id)
    assert chegada.payload["chegou_em"] == alvo.chegou_em.isoformat()

    iminencia = db_session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == proximo.id, NotificacaoAgendada.tipo == NotificacaoTipo.IMINENCIA
        )
    ).one()
    assert iminencia.payload["trip_student_id"] == str(proximo.id)
    assert iminencia.payload["aluno_id"] == str(proximo.aluno_id)


def test_payload_de_preparo_inclui_ids_de_roteamento_na_criacao_e_no_reagendamento(db_session):
    cenario = _criar_cenario(db_session, n_paradas=3)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1, ts3 = ts_list[0], ts_list[2]

    ts1.estado = TripStudentEstado.CHEGOU
    ts1.chegou_em = _dt(100)
    evento = tsm.registrar_checkin(viagem, ts1, ocorrido_em=_dt(150), registrado_em=_dt(150))
    db_session.add(evento)
    pos_evento.processar_checkin(db_session, viagem, ts_list, ts1, _dt(150), sender=StubFCMSender())
    db_session.commit()

    preparo = db_session.scalars(
        select(NotificacaoAgendada).where(
            NotificacaoAgendada.trip_student_id == ts3.id, NotificacaoAgendada.tipo == NotificacaoTipo.PREPARO
        )
    ).one()
    assert preparo.payload["trip_student_id"] == str(ts3.id)
    assert preparo.payload["aluno_id"] == str(ts3.aluno_id)
    assert preparo.payload["viagem_id"] == str(viagem.id)
    assert "faixa_min_baixo" in preparo.payload  # payload de domínio preservado, não substituído

    # "Estou atrasado" força `_recalcular_e_reagendar`, que reescreve o
    # payload do preparo pendente — os ids de roteamento têm que sobreviver.
    pos_evento.processar_estou_atrasado(db_session, viagem, ts_list, 5, _dt(200))
    db_session.commit()
    db_session.refresh(preparo)
    assert preparo.payload["trip_student_id"] == str(ts3.id)


def test_checkin_dispara_dismiss_chegada(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1 = ts_list[0]
    resp_ts1 = cenario["responsaveis_por_aluno"][ts1.aluno_id]

    ts1.estado = TripStudentEstado.CHEGOU
    ts1.chegou_em = _dt(100)
    evento = tsm.registrar_checkin(viagem, ts1, ocorrido_em=_dt(150), registrado_em=_dt(150))
    db_session.add(evento)
    sender = StubFCMSender()
    pos_evento.processar_checkin(db_session, viagem, ts_list, ts1, _dt(150), sender=sender)
    db_session.commit()

    dismiss = [e for e in sender.enviadas if e["tipo"] == "dismiss_chegada"]
    assert len(dismiss) == 1
    assert dismiss[0]["destinatario_user_id"] == resp_ts1.user_id
    assert dismiss[0]["payload"]["trip_student_id"] == str(ts1.id)


def test_ausente_vindo_de_chegou_dispara_dismiss_mas_de_aguardando_nao(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts_direto, ts_via_chegou = ts_list[0], ts_list[1]

    # ts_direto: aguardando -> ausente (nunca existiu notificação persistente).
    evento1 = tsm.registrar_ausente(viagem, ts_direto, ocorrido_em=_dt(50), registrado_em=_dt(50))
    db_session.add(evento1)
    sender1 = StubFCMSender()
    pos_evento.processar_ausente(db_session, viagem, ts_list, ts_direto, _dt(50), sender=sender1)
    db_session.commit()
    assert [e for e in sender1.enviadas if e["tipo"] == "dismiss_chegada"] == []

    # ts_via_chegou: aguardando -> chegou -> ausente (a persistente existiu).
    ts_via_chegou.estado = TripStudentEstado.CHEGOU
    ts_via_chegou.chegou_em = _dt(60)
    evento2 = tsm.registrar_ausente(viagem, ts_via_chegou, ocorrido_em=_dt(80), registrado_em=_dt(80))
    db_session.add(evento2)
    sender2 = StubFCMSender()
    pos_evento.processar_ausente(db_session, viagem, ts_list, ts_via_chegou, _dt(80), sender=sender2)
    db_session.commit()

    dismiss = [e for e in sender2.enviadas if e["tipo"] == "dismiss_chegada"]
    assert len(dismiss) == 1
    assert dismiss[0]["payload"]["trip_student_id"] == str(ts_via_chegou.id)
