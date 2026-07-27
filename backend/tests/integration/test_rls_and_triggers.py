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

from app.api.deps import get_tenant_db
from app.core.db import engine
from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.schemas.auth import CurrentUser
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
    viagem_id = uuid.uuid4()
    viagem = Viagem(
        id=viagem_id, tenant_id=cenario["tenant_id"], rota_id=cenario["rota_id"],
        veiculo_id=cenario["veiculo_id"], motorista_id=cenario["motorista_id"],
        data=datetime.date(2026, 7, 27), status=ViagemStatus.PLANEJADA,
    )
    db_session.add(viagem)
    db_session.commit()

    clear_tenant(db_session)
    # Usa `viagem_id` (guardado antes do commit), não `viagem.id`: o commit
    # expira os atributos do objeto (expire_on_commit=True), e lê-lo agora —
    # dentro da transação com o tenant já limpo — dispararia um refresh que
    # o RLS torna invisível, virando `ObjectDeletedError` em vez de zero
    # linhas (o objeto não foi deletado, só ficou fora do escopo do tenant).
    resultado = db_session.query(Viagem).filter(Viagem.id == viagem_id).all()
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
        ocorrido_em=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all(novos)
    db_session.commit()

    aluno_ts = novos[0]
    agora = datetime.datetime.now(datetime.timezone.utc)
    evento = tsm.registrar_cheguei(
        viagem, aluno_ts, [aluno_ts], ocorrido_em=agora, registrado_em=agora
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
    novos = tsm.iniciar_viagem(viagem, [(cenario["aluno_id"], cenario["parada_id"], 1)], ocorrido_em=now)
    db_session.add_all(novos)
    db_session.commit()

    aluno_ts = novos[0]

    for acao in ("registrar_cheguei", "registrar_checkin", "registrar_checkout"):
        fn = getattr(tsm, acao)
        agora = datetime.datetime.now(datetime.timezone.utc)
        if acao == "registrar_cheguei":
            evento = fn(viagem, aluno_ts, [aluno_ts], ocorrido_em=agora, registrado_em=agora)
        else:
            evento = fn(viagem, aluno_ts, ocorrido_em=agora, registrado_em=agora)
        db_session.add(evento)
        db_session.commit()

    assert aluno_ts.estado == TripStudentEstado.ENTREGUE

    tsm.finalizar_viagem(viagem, [aluno_ts], ocorrido_em=datetime.datetime.now(datetime.timezone.utc))
    db_session.commit()

    assert viagem.status == ViagemStatus.FINALIZADA
    assert viagem.varredura_confirmada is True


# ---------------------------------------------------------------------------
# Regressão — set_config escopo de transação (portão B1->B2, achado runtime)
#
# `app/api/deps.py::get_tenant_db` usava `set_config(..., false)` (escopo de
# SESSÃO). Numa engine com pool de conexões, isso deixa o `app.tenant_id` de
# um request grudado na conexão física depois do COMMIT — disponível para o
# próximo request que reaproveitar essa conexão. Estes testes travam a
# correção (`true`, escopo de transação) e o efeito colateral dela (migration
# 0006 — GUC placeholder tocada reseta para `''`, não `NULL`).
# ---------------------------------------------------------------------------


def test_set_config_local_nao_vaza_para_proxima_transacao_na_mesma_conexao(db_session):
    """Duas transações seguidas na MESMA conexão física, tenants diferentes —
    a segunda, sem setar tenant, tem que enxergar ZERO linhas (fail-closed),
    nunca as linhas do tenant da transação anterior.

    Usa `engine.connect()` bruto (não a Session do ORM) para controlar as
    fronteiras BEGIN/COMMIT com precisão e garantir que é literalmente a
    mesma conexão física nas duas transações — é o cenário do pool de
    conexões reaproveitado entre requests de tenants diferentes.
    """
    cenario = _criar_cenario_basico(db_session)
    tenant_id = str(cenario["tenant_id"])

    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id})
            vistas = conn.execute(text("SELECT count(*) FROM rotas")).scalar_one()
            assert vistas == 1, "com o tenant setado, a rota do cenário deve aparecer"

        # Nova transação, MESMA conexão física — ninguém chamou set_config de novo.
        with conn.begin():
            vistas = conn.execute(text("SELECT count(*) FROM rotas")).scalar_one()
            assert vistas == 0, (
                "RLS fail-closed: sem tenant setado nesta transação, zero linhas — "
                "nunca as do tenant anterior (era isso que `false`/escopo de sessão quebrava)."
            )


def test_set_config_local_guc_tocada_e_resetada_nao_gera_erro_de_cast(db_session):
    """Efeito colateral descoberto ao validar o fix acima: uma GUC placeholder
    (`app.tenant_id`) que já foi tocada na conexão volta para string vazia
    (`''`) no reset, não `NULL`. Sem a blindagem `NULLIF(..., '')` na política
    (migration 0006), o cast `::uuid` bruto quebraria com
    `invalid input syntax for type uuid: ""` em vez de fail-closed silencioso.
    """
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(uuid.uuid4())})

        with conn.begin():
            valor = conn.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar_one()
            assert valor == "", "confirma a premissa: reset de GUC já tocada vira string vazia, não NULL"

            # Sem a migration 0006, esta linha levantaria ProgrammingError
            # ("invalid input syntax for type uuid") em vez de devolver 0.
            vistas = conn.execute(text("SELECT count(*) FROM rotas")).scalar_one()
            assert vistas == 0


def test_get_tenant_db_reaplica_tenant_apos_commit_no_meio_do_request(db_session):
    """Dentro de UM request (uma chamada a `get_tenant_db`), se o handler der
    mais de um `commit()` (padrão comum nas rotas de `viagens.py`/`alunos.py`),
    o tenant precisa continuar aplicado nas transações seguintes — não só na
    primeira.

    Sem o listener `after_begin` em `get_tenant_db`, um `set_config` único no
    início do generator morreria no primeiro `commit()` (escopo local) e a
    segunda query do mesmo request voltaria zero linhas silenciosamente.
    """
    cenario = _criar_cenario_basico(db_session)

    current_user = CurrentUser(
        id=uuid.uuid4(), tenant_id=cenario["tenant_id"], email="teste@teste.com", role=UserRole.ADMIN,
    )

    gen = get_tenant_db(current_user)
    session = next(gen)
    try:
        primeira = session.execute(text("SELECT count(*) FROM rotas")).scalar_one()
        assert primeira == 1

        session.commit()  # fecha a 1ª transação — a 2ª abre via autobegin na próxima query

        segunda = session.execute(text("SELECT count(*) FROM rotas")).scalar_one()
        assert segunda == 1, "tenant tem que continuar aplicado após o commit no meio do request"
    finally:
        gen.close()
