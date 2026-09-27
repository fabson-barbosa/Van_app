"""Conexão com o banco (SQLAlchemy) e dependência de sessão para o FastAPI."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Pool dimensionado para Cloud Run + Cloud SQL, não para um processo só.
#
# Cada instância do Cloud Run tem o SEU pool. O padrão do SQLAlchemy
# (pool_size=5 + max_overflow=10) permite 15 conexões por instância — com
# `--max-instances=4` viram 60, e o menor tier do Cloud SQL (db-f1-micro) aceita
# 25 no total, contando ainda o job de migration e o job do agendador. O
# resultado seria "FATAL: remaining connection slots are reserved" sob pico, que
# é exatamente quando o motorista está registrando embarque.
#
# 3 por instância (2 + 1 de folga) × 4 instâncias = 12, com margem confortável.
# Ajustável por env var para quem subir num tier maior; ver `deploy/README.md`.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # descarta conexão morta pelo idle timeout do Cloud SQL
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    # O Cloud SQL encerra conexões ociosas; reciclar antes evita que o
    # `pool_pre_ping` pague um round-trip perdido em toda requisição de rota
    # depois de um período sem tráfego.
    pool_recycle=1800,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Base declarativa de todos os models SQLAlchemy."""


def get_db() -> Generator[Session, None, None]:
    """Dependência FastAPI: abre uma sessão por request e garante o fechamento.

    ATENÇÃO — esta sessão NÃO seta `app.tenant_id`. NÃO use em nenhuma rota
    que leia ou escreva tabelas com coluna `tenant_id` (RLS fail-closed faz
    essas queries voltarem zero linhas silenciosamente, não um erro óbvio).
    Use `app.api.deps.get_tenant_db` para isso.

    O único uso legítimo de `get_db` hoje é o login (`app/api/auth.py`), que
    precisa localizar o usuário por e-mail ANTES de saber o tenant — ver o
    comentário em `migrations/versions/0001_initial_schema.py` sobre por que
    `users` foi deixada fora do RLS de propósito.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
