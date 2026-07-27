"""Fixtures dos testes de integração (RLS + trigger de imutabilidade).

Exigem um Postgres+PostGIS real e descartável, apontado por `DATABASE_URL`/
`.env` (ver CLAUDE.md §9, "Portão de validação antes do B2" — quitado via
docker-compose local; ver PROGRESSO.md). Por isso todo teste aqui é
`@pytest.mark.integration`: não roda no `pytest` padrão, só com
`pytest -m integration` contra um banco de teste.

IMPORTANTE — o `DATABASE_URL` usado para rodar este arquivo (via `.env` ou
env var) deve ser o role de aplicação (`vaivem_app`), não o owner (`vaivem`):
o owner é criado como superuser pela imagem oficial do Postgres e superusers
sempre ignoram RLS (`FORCE ROW LEVEL SECURITY` só remove a isenção do dono da
tabela, não afeta `BYPASSRLS`) — rodar os testes como owner faria os
asserts de fail-closed passarem por motivo errado (ou nem passarem, já que
owner vê tudo). Migrations, porém, exigem privilégio de owner (CREATE TABLE,
CREATE POLICY, CREATE EXTENSION) — por isso o fixture abaixo sempre roda o
`alembic upgrade head` com a URL do owner, independente do `DATABASE_URL`
usado pelo resto da suíte.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import event, text

from app.core.db import SessionLocal

BACKEND_DIR = Path(__file__).resolve().parents[2]

_OWNER_DATABASE_URL = os.environ.get(
    "OWNER_DATABASE_URL", "postgresql+psycopg://vaivem:vaivem@localhost:5432/vaivem"
)


@pytest.fixture(scope="session", autouse=True)
def _alembic_upgrade_head():
    env = {**os.environ, "DATABASE_URL": _OWNER_DATABASE_URL}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True, env=env)
    yield


def _reaplicar_tenant_no_begin(session, transaction, connection) -> None:
    """Espelha `app/api/deps.py::get_tenant_db`: `set_config(..., true)` é
    escopo de TRANSAÇÃO, então precisa ser reaplicado toda vez que uma
    transação nova começa nesta sessão — não só na primeira (um teste pode
    dar vários `commit()` no meio, cada um fecha a transação corrente e a
    próxima query reabre uma nova via autobegin do SQLAlchemy).
    """
    tenant_id = session.info.get("tenant_id")
    if tenant_id is not None:
        connection.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id})


@pytest.fixture()
def db_session():
    session = SessionLocal()
    event.listen(session, "after_begin", _reaplicar_tenant_no_begin)
    try:
        yield session
    finally:
        event.remove(session, "after_begin", _reaplicar_tenant_no_begin)
        session.rollback()
        session.close()


def set_tenant(session, tenant_id: uuid.UUID) -> None:
    """Seta o tenant para o resto do teste — sobrevive a `commit()`s
    subsequentes na mesma `db_session` graças ao listener `after_begin`
    acima, que reaplica a cada nova transação a partir de `session.info`.
    """
    session.info["tenant_id"] = str(tenant_id)
    # Aplica imediatamente também na transação já em andamento, se houver —
    # o listener só dispara em transações NOVAS a partir daqui.
    session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)})


def clear_tenant(session) -> None:
    session.info["tenant_id"] = None
    session.execute(text("SELECT set_config('app.tenant_id', '', true)"))
