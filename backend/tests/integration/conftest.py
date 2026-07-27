"""Fixtures dos testes de integração (RLS + trigger de imutabilidade).

Exigem um Postgres+PostGIS real e descartável, apontado por `DATABASE_URL`/
`.env` (ver CLAUDE.md §9, "Portão de validação antes do B2" — pendente neste
ambiente, sem Postgres disponível). Por isso todo teste aqui é
`@pytest.mark.integration`: não roda no `pytest` padrão, só com
`pytest -m integration` contra um banco de teste.
"""
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.db import SessionLocal

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def _alembic_upgrade_head():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND_DIR, check=True)
    yield


@pytest.fixture()
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def set_tenant(session, tenant_id: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.tenant_id', :tid, false)"), {"tid": str(tenant_id)})


def clear_tenant(session) -> None:
    session.execute(text("SELECT set_config('app.tenant_id', '', false)"))
