"""Testes de integração — RLS fail-closed e trigger de imutabilidade (Bloco B2).

Cobrem o "Portão de validação antes do B2" do CLAUDE.md §9 (pendente neste
ambiente — sem Postgres disponível) mais o fluxo ponta-a-ponta da máquina de
estados contra o banco real. Rodar com:

    pytest -m integration

contra um Postgres+PostGIS de teste (DATABASE_URL no .env).
"""
import datetime
import uuid

import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.services import trip_state_machine as tsm
from tests.integration.conftest import clear_tenant, set_tenant

pytestmark = pytest.mark.integration


def _criar_cenario_basico(session):
    """Tenant + 1 rota + 1 parada + 1 aluno + 1 motorista + 1 veículo, prontos
    para montar uma viagem. Retorna um dict de ids."""
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Teste {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista Teste",
        email=f"motorista.{uuid.uuid4()}@teste.com", senha_hash=hash_password("x"),
        role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()

    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)

    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="TST0001", km_atual=0)
    session.add(veiculo)

    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota Teste", turno="manha", ativa=True)
    session.add(rota)
    session.flush()

    parada = Parada(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome="Parada 1", ordem_base=1,
        geo=from_shape(Point(-46.63, -23.55), srid=4326),
    )
    session.add(parada)
    session.flush()

    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome="Aluno Teste", parada_id=parada.id, ativo=True)
    session.add(aluno)
    session.flush()

    session.commit()
    return {
        "tenant_id": tenant.id,
        "rota_id": rota.id,
        "parada_id": parada.id,
        "aluno_id": aluno.id,
        "motorista_id": motorista.id,
        "veiculo_id": veiculo.id,
    }


# ---------------------------------------------------------------------------
# RLS fail-closed
# ---------------------------------------------------------------------------


def test_rls_fail_closed_sem_tenant_setado(db_session):
    cenario = _criar_cenario_basico(db_session)

    set_tenant(db_session, cenario["tenant_id"])
    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=cenario["tenant_id"], rota_id=cenario["rota_id"],
        veiculo_id=cenario["veiculo_id"], motorista_id=cenario["motorista_id"],
        data=datetime.date(2026, 7, 27), status=ViagemStatus.PLANEJADA,
    )
    db_session.add(viagem)
    db_session.commit()

    clear_tenant(db_session)
    resultado = db_session.query(Viagem).filter(Viagem.id == viagem.id).all()
    assert resultado == [], "RLS deve ser fail-closed: sem app.tenant_id, zero linhas — nunca todas."


# ---------------------------------------------------------------------------
# Trigger de imutabilidade em eventos_aluno
# ---------------------------------------------------------------------------


def test_trigger_rejeita_update_em_eventos_aluno(db_session):
    cenario = _criar_cenario_basico(db_session)
    set_tenant(db_session, cenario["tenant_id"])

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=cenario["tenant_id"], rota_id=cenario["rota_id"],
        veiculo_id=cenario["veiculo_id"], motorista_id=cenario["motorista_id"],
        data=datetime.date(2026, 7, 27), status=ViagemStatus.PLANEJADA,
    )
    db_session.add(viagem)
    db_session.flush()

    novos = tsm.iniciar_viagem(
        viagem, [(cenario["aluno_id"], cenario["parada_id"], 1)],
        now=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all(novos)
    db_session.commit()

    aluno_ts = novos[0]
    evento = tsm.registrar_cheguei(
        viagem, aluno_ts, [aluno_ts], now=datetime.datetime.now(datetime.timezone.utc)
    )
    db_session.add(evento)
    db_session.commit()

    with pytest.raises(DBAPIError):
        db_session.execute(
            text("UPDATE eventos_aluno SET device_timestamp = now() WHERE id = :id"),
            {"id": str(evento.id)},
        )
        db_session.commit()
    db_session.rollback()

    with pytest.raises(DBAPIError):
        db_session.execute(text("DELETE FROM eventos_aluno WHERE id = :id"), {"id": str(evento.id)})
        db_session.commit()
    db_session.rollback()


# ---------------------------------------------------------------------------
# Fluxo ponta-a-ponta do B2 contra o banco real
# ---------------------------------------------------------------------------


def test_fluxo_completo_iniciar_cheguei_checkin_checkout_finalizar(db_session):
    cenario = _criar_cenario_basico(db_session)
    set_tenant(db_session, cenario["tenant_id"])

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=cenario["tenant_id"], rota_id=cenario["rota_id"],
        veiculo_id=cenario["veiculo_id"], motorista_id=cenario["motorista_id"],
        data=datetime.date(2026, 7, 27), status=ViagemStatus.PLANEJADA,
    )
    db_session.add(viagem)
    db_session.flush()

    now = datetime.datetime.now(datetime.timezone.utc)
    novos = tsm.iniciar_viagem(viagem, [(cenario["aluno_id"], cenario["parada_id"], 1)], now=now)
    db_session.add_all(novos)
    db_session.commit()

    aluno_ts = novos[0]

    for acao in ("registrar_cheguei", "registrar_checkin", "registrar_checkout"):
        fn = getattr(tsm, acao)
        agora = datetime.datetime.now(datetime.timezone.utc)
        if acao == "registrar_cheguei":
            evento = fn(viagem, aluno_ts, [aluno_ts], now=agora)
        else:
            evento = fn(viagem, aluno_ts, now=agora)
        db_session.add(evento)
        db_session.commit()

    assert aluno_ts.estado == TripStudentEstado.ENTREGUE

    tsm.finalizar_viagem(viagem, [aluno_ts], now=datetime.datetime.now(datetime.timezone.utc))
    db_session.commit()

    assert viagem.status == ViagemStatus.FINALIZADA
    assert viagem.varredura_confirmada is True
