"""Teste de integração obrigatório (Bloco B4, aprovado pelo usuário antes da
implementação): a migration `0008_reconciliacao_temporal` precisa rodar sobre
uma base COM dados reais em `eventos_aluno`/`trip_students`, não só vazia —
é exatamente aí que o achado do trigger de imutabilidade aparece (o backfill
do rename `timestamp`->`ocorrido_em` é um UPDATE, e o trigger de `0004`
bloqueia UPDATE mesmo pro owner da migração).

Estratégia: monta o grafo de suporte (tenant/user/motorista/veículo/rota/
aluno/viagem/trip_student) via ORM normalmente (essas tabelas não mudam nesta
migration), depois faz `alembic downgrade` para ANTES da 0008 — o que
desfaz o rename e derruba as colunas novas —, insere a linha de
`eventos_aluno` via SQL cru no formato PRÉ-migration (coluna `timestamp`,
sem `event_id`), e só então roda `alembic upgrade head` de novo, conferindo:

1. o backfill preencheu `ocorrido_em`/`registrado_em`/`event_id` corretamente;
2. o trigger de imutabilidade CONTINUA bloqueando UPDATE/DELETE depois de ter
   sido desligado/religado dentro da própria migração;
3. `trip_students.checkin_registrado_em` existe (NULL para o registro que já
   existia antes da migração — sem fonte de backfill, fail-safe no
   `desfazer_checkin`, ver `app/services/trip_state_machine.py`).

Um `finally` garante `alembic upgrade head` mesmo se alguma asserção falhar —
o fixture `_alembic_upgrade_head` do `conftest.py` só roda `upgrade head` UMA
vez, no início da sessão de testes; se este teste terminasse com o schema
desatualizado, todo teste de integração seguinte quebraria.
"""
import datetime
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.db import engine
from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.motorista import Motorista
from app.models.rota import Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]
_OWNER_DATABASE_URL = os.environ.get(
    "OWNER_DATABASE_URL", "postgresql+psycopg://vaivem:vaivem@localhost:5432/vaivem"
)
_REVISAO_ANTERIOR = "0007_notificacoes_e_estimativas"


def _alembic(*args: str) -> None:
    env = {**os.environ, "DATABASE_URL": _OWNER_DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND_DIR, check=True, env=env)


def _montar_grafo_de_suporte(session):
    """Tenant + user/motorista + veículo + rota + aluno + viagem + trip_student
    — nenhuma dessas tabelas muda na 0008, então montá-las via ORM (a HEAD)
    antes de fazer o downgrade é seguro: o downgrade só afeta `eventos_aluno`
    e a coluna nova de `trip_students`."""
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Migration 0008 {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista Migration", email=f"mig.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()

    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)
    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="MIG0008", km_atual=0)
    session.add(veiculo)
    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota Migration 0008", turno="manha", ativa=True)
    session.add(rota)
    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome="Aluno Migration", parada_id=None, ativo=True)
    session.add(aluno)
    session.flush()

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=datetime.date(2026, 7, 20), status=ViagemStatus.EM_ANDAMENTO,
        iniciada_em=datetime.datetime(2026, 7, 20, 7, 0, 0, tzinfo=datetime.timezone.utc),
    )
    session.add(viagem)
    session.flush()

    trip_student = TripStudent(
        id=uuid.uuid4(), tenant_id=tenant.id, viagem_id=viagem.id, aluno_id=aluno.id, parada_id=None,
        ordem=1, estado=TripStudentEstado.AGUARDANDO,
    )
    session.add(trip_student)
    session.flush()

    # Captura os ids ANTES do commit — depois do commit, `expire_on_commit`
    # (padrão do SQLAlchemy) expira os atributos, e acessar `.id` disparia um
    # refresh implícito que ABRE UMA NOVA TRANSAÇÃO nesta sessão. Essa
    # transação ficaria "idle in transaction" segurando um AccessShareLock em
    # `trip_students` pelo resto do teste — e como o teste faz `alembic
    # downgrade` logo em seguida (que precisa de AccessExclusiveLock na MESMA
    # tabela pra rodar `ALTER TABLE ... DROP COLUMN`), isso é um deadlock da
    # sessão contra o próprio subprocesso da migração (achado rodando de
    # verdade contra o Postgres do docker-compose — não aparecia em nenhum
    # teste anterior porque nenhum outro combina ORM + DDL fora de processo).
    tenant_id, trip_student_id = tenant.id, trip_student.id
    session.commit()

    return tenant_id, trip_student_id


def test_migration_0008_com_eventos_existentes_faz_backfill_e_preserva_trigger(db_session):
    tenant_id, trip_student_id = _montar_grafo_de_suporte(db_session)
    evento_id = uuid.uuid4()
    momento_original = datetime.datetime(2026, 7, 20, 8, 0, 0, tzinfo=datetime.timezone.utc)

    try:
        _alembic("downgrade", _REVISAO_ANTERIOR)

        # Insere via SQL cru, no formato PRÉ-0008 (`timestamp`, sem `event_id`) —
        # nenhum model Python atual mapeia mais esse formato.
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
                conn.execute(
                    text(
                        "INSERT INTO eventos_aluno "
                        "(id, tenant_id, trip_student_id, tipo, estado_anterior, timestamp, device_timestamp) "
                        "VALUES (:id, :tid, :tsid, 'cheguei', 'aguardando', :momento, NULL)"
                    ),
                    {
                        "id": str(evento_id), "tid": str(tenant_id), "tsid": str(trip_student_id),
                        "momento": momento_original,
                    },
                )

        _alembic("upgrade", "head")

        with engine.connect() as conn:
            with conn.begin():
                conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})

                linha = conn.execute(
                    text("SELECT ocorrido_em, registrado_em, event_id FROM eventos_aluno WHERE id = :id"),
                    {"id": str(evento_id)},
                ).one()
                assert linha.ocorrido_em == momento_original, "rename timestamp->ocorrido_em deveria preservar o valor"
                assert linha.registrado_em == momento_original, "backfill deveria copiar ocorrido_em para registrado_em"
                assert linha.event_id is not None, "backfill deveria gerar um event_id novo"

                checkin_registrado_em = conn.execute(
                    text("SELECT checkin_registrado_em FROM trip_students WHERE id = :id"),
                    {"id": str(trip_student_id)},
                ).scalar_one()
                assert checkin_registrado_em is None, "sem fonte de backfill — deve ficar NULL (fail-safe)"

            # Trigger de imutabilidade: religado pela migration, tem que continuar
            # bloqueando UPDATE e DELETE (mesma prova de `test_rls_and_triggers.py`).
            with pytest.raises(Exception):
                with conn.begin():
                    conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
                    conn.execute(
                        text("UPDATE eventos_aluno SET device_timestamp = now() WHERE id = :id"),
                        {"id": str(evento_id)},
                    )

            with pytest.raises(Exception):
                with conn.begin():
                    conn.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})
                    conn.execute(text("DELETE FROM eventos_aluno WHERE id = :id"), {"id": str(evento_id)})
    finally:
        _alembic("upgrade", "head")
