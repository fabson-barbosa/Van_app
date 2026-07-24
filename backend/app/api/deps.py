"""Dependências FastAPI compartilhadas: usuário autenticado + sessão de banco
já configurada para RLS (seta `app.tenant_id` na sessão Postgres).

Fluxo (Fase 1 — RBAC simples baseado em claims do JWT):
1. `get_current_user` decodifica o token e devolve um `CurrentUser`.
2. `get_tenant_db` abre uma sessão e executa `set_config('app.tenant_id', ...)`,
   fazendo a política de RLS (migration 0001) filtrar automaticamente todas
   as queries dessa sessão pelo tenant do usuário autenticado.

Sem isso, a política `tenant_isolation_*` (fail-closed) bloquearia tudo.
"""
import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import decode_access_token
from app.schemas.auth import CurrentUser

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou expiradas.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str | None = Depends(_oauth2_scheme)) -> CurrentUser:
    if token is None:
        raise _CREDENTIALS_ERROR

    payload = decode_access_token(token)
    if payload is None:
        raise _CREDENTIALS_ERROR

    try:
        return CurrentUser(
            id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tenant_id"]),
            email=payload["email"],
            role=payload["role"],
        )
    except (KeyError, ValueError) as exc:
        raise _CREDENTIALS_ERROR from exc


def get_tenant_db(
    current_user: CurrentUser = Depends(get_current_user),
) -> Generator[Session, None, None]:
    """Sessão de banco com `app.tenant_id` setado — RLS faz o resto.

    Use esta dependência (em vez de `get_db`) em qualquer rota que leia/escreva
    dados pertencentes a um tenant.
    """
    db = SessionLocal()
    try:
        # `SET app.tenant_id = :param` não é aceito pelo driver (SET não suporta
        # bind parameters — gera "syntax error at or near $1"). `set_config` é a
        # forma correta de setar uma GUC com parâmetro via prepared statement.
        db.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, false)"),
            {"tenant_id": str(current_user.tenant_id)},
        )
        yield db
    finally:
        db.close()


def require_role(*allowed_roles: str):
    """Factory de dependência: garante que o usuário tem um dos papéis permitidos.

    Ex.: `Depends(require_role("admin"))` — RBAC simples (arquitetura.md, 3.5).
    """

    def _check(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role.value not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não tem permissão para acessar este recurso.",
            )
        return current_user

    return _check
