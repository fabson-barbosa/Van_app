"""Conexão com o banco (SQLAlchemy) e dependência de sessão para o FastAPI."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

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
