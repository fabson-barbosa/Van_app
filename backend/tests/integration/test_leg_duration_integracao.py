"""Testes de integração — motor de trajeto contra Postgres real (Bloco B3).

Complementa `tests/test_leg_duration.py` (puro): aqui a preocupação é a parte
que só existe com banco — persistência da amostra em `leg_durations` e a
agregação SQL (`SUM`/média ponderada) por trás de `escolher_estimativa`.
"""
import datetime
import uuid

from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

import pytest

from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.leg_duration import LegDuration
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)  # segunda-feira


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _criar_cenario(session, n_paradas: int = 3):
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant LD {uuid.uuid4()}", plano="pro", status_billing="ativo")
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
    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="LD00001", km_atual=0)
    session.add(veiculo)
    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota LD", turno="manha", ativa=True)
    session.add(rota)
    session.flush()

    alunos_paradas = []
    for i in range(1, n_paradas + 1):
        parada = Parada(
            id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome=f"Parada {i}", ordem_base=i,
            geo=from_shape(Point(-46.6 + i * 0.001, -23.5), srid=4326),
        )
        session.add(parada)
        session.flush()
        aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome=f"Aluno {i}", parada_id=parada.id, ativo=True)
        session.add(aluno)
        session.flush()
        alunos_paradas.append((aluno.id, parada.id, i))

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.PLANEJADA,
    )
    session.add(viagem)
    session.flush()
    novos = tsm.iniciar_viagem(viagem, alunos_paradas, ocorrido_em=T0)
    session.add_all(novos)
    session.commit()

    trip_students = sorted(
        session.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id)), key=lambda ts: ts.ordem
    )
    return {"tenant_id": tenant.id, "rota_id": rota.id, "viagem": viagem, "trip_students": trip_students}


def _leg_duration(session, rota_id, ordem, momento):
    return session.scalars(
        select(LegDuration).where(
            LegDuration.rota_id == rota_id, LegDuration.ordem == ordem,
            LegDuration.dia_semana == momento.weekday(), LegDuration.faixa_horaria == momento.hour,
        )
    ).first()


def test_cheguei_na_primeira_parada_usa_iniciada_em_como_ancora(db_session):
    cenario = _criar_cenario(db_session, n_paradas=2)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1 = ts_list[0]

    evento = tsm.registrar_cheguei(viagem, ts1, ts_list, ocorrido_em=_dt(300), registrado_em=_dt(300))
    db_session.add(evento)
    pos_evento.processar_cheguei(db_session, viagem, ts_list, ts1, _dt(300))
    db_session.commit()

    bucket = _leg_duration(db_session, cenario["rota_id"], 1, _dt(300))
    assert bucket is not None
    assert bucket.amostras == 1
    # EWMA: 0.3*300 + 0.7*240(semente padrão) = 90+168 = 258
    assert bucket.segundos_media == pytest.approx(258.0)


def test_casa_pulada_nao_vira_amostra_de_trajeto(db_session):
    cenario = _criar_cenario(db_session, n_paradas=3)
    viagem, ts_list = cenario["viagem"], cenario["trip_students"]
    set_tenant(db_session, cenario["tenant_id"])
    ts1, ts2, ts3 = ts_list

    # aluno 2 é pulado — ausente direto de aguardando, sem chegou_em/checkin_em
    evento_ausente = tsm.registrar_ausente(viagem, ts2, ocorrido_em=_dt(50), registrado_em=_dt(50))
    db_session.add(evento_ausente)
    pos_evento.processar_ausente(db_session, viagem, ts_list, ts2, _dt(50))
    db_session.commit()

    # Cheguei(3) — o trecho anterior (até a parada 2, pulada) não pode virar amostra
    evento_cheguei = tsm.registrar_cheguei(viagem, ts3, ts_list, ocorrido_em=_dt(600), registrado_em=_dt(600))
    db_session.add(evento_cheguei)
    pos_evento.processar_cheguei(db_session, viagem, ts_list, ts3, _dt(600))
    db_session.commit()

    assert _leg_duration(db_session, cenario["rota_id"], 2, _dt(50)) is None
    assert _leg_duration(db_session, cenario["rota_id"], 3, _dt(600)) is None


def test_agregacao_progressiva_usa_bucket_exato_com_5_ou_mais_amostras(db_session):
    cenario = _criar_cenario(db_session, n_paradas=1)
    set_tenant(db_session, cenario["tenant_id"])
    rota_id = cenario["rota_id"]

    # bucket exato (mesmo dia_semana/faixa_horaria de T0) já com 5 amostras —
    # chave única é (rota,ordem,dia,faixa), então é UMA linha com amostras=5,
    # não 5 linhas (a agregação de "quantas amostras" já está na coluna).
    db_session.add(LegDuration(
        tenant_id=cenario["tenant_id"], rota_id=rota_id, ordem=1,
        dia_semana=T0.weekday(), faixa_horaria=T0.hour, segundos_media=200.0, amostras=5,
    ))
    # bucket "geral" (outro dia/faixa) com valor bem diferente — não deve vencer.
    outro_dia = (T0.weekday() + 1) % 7
    db_session.add(LegDuration(
        tenant_id=cenario["tenant_id"], rota_id=rota_id, ordem=1,
        dia_semana=outro_dia, faixa_horaria=T0.hour, segundos_media=999.0, amostras=20,
    ))
    db_session.commit()

    estimativa = pos_evento.prever_segundos_leg(db_session, rota_id, 1, T0, estimativa_seed_segundos=240)
    assert estimativa == pytest.approx(200.0)


def test_agregacao_progressiva_cai_para_nivel_geral_sem_amostras_no_dia(db_session):
    cenario = _criar_cenario(db_session, n_paradas=1)
    set_tenant(db_session, cenario["tenant_id"])
    rota_id = cenario["rota_id"]

    outro_dia = (T0.weekday() + 1) % 7
    db_session.add(LegDuration(
        tenant_id=cenario["tenant_id"], rota_id=rota_id, ordem=1,
        dia_semana=outro_dia, faixa_horaria=T0.hour, segundos_media=180.0, amostras=8,
    ))
    db_session.commit()

    estimativa = pos_evento.prever_segundos_leg(db_session, rota_id, 1, T0, estimativa_seed_segundos=240)
    # nada no bucket exato (dia de T0) nem no dia de T0 — cai pro geral (só a linha de outro_dia), amostras=8 >=...
    # geral agrega TODAS as linhas do (rota,ordem) independente do dia — inclui essa.
    assert estimativa == pytest.approx(180.0)
