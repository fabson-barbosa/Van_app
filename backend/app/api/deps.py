"""Dependências FastAPI compartilhadas: usuário autenticado + sessão de banco
já configurada para RLS (seta `app.tenant_id` na sessão Postgres).

Fluxo (Fase 1 — RBAC simples baseado em claims do JWT):
1. `get_current_user` decodifica o token e devolve um `CurrentUser`.
2. `get_tenant_db` abre uma sessão e usa `set_config('app.tenant_id', ..., true)`
   — escopo de TRANSAÇÃO, não de sessão — fazendo a política de RLS
   (migrations 0001-0006) filtrar automaticamente todas as queries dessa
   sessão pelo tenant do usuário autenticado.

Sem isso, a política `tenant_isolation_*` (fail-closed) bloquearia tudo.

IMPORTANTE — por que `true` (escopo de transação) e não `false` (escopo de
sessão): a engine usa um pool de conexões (`app/core/db.py`), então uma
conexão física é reaproveitada entre requests de tenants diferentes ao longo
do tempo. Com `false`, o `app.tenant_id` setado por um request sobrevive ao
`COMMIT` e fica "grudado" na conexão até o próximo `set_config` — qualquer
código futuro que reutilize essa conexão sem passar por `get_tenant_db`
(um novo endpoint com `get_db` bruto, um script, uma falha entre o checkout
da conexão e a chamada do `set_config`) herdaria silenciosamente o tenant do
request anterior em vez de falhar fechado. Com `true`, a GUC é automaticamente
resetada no `COMMIT`/`ROLLBACK` da transação — a pior consequência de um
descuido futuro é RLS fail-closed (zero linhas), nunca vazamento entre
tenants. Ver `tests/integration/test_rls_and_triggers.py` para o teste de
regressão que prova essa propriedade.

Como uma única sessão pode abrir MAIS de uma transação por request (cada
`db.commit()` de um endpoint fecha a corrente; a próxima query reabre uma
nova via autobegin do SQLAlchemy), setar `app.tenant_id` uma única vez no
início do generator não basta — o listener `after_begin` abaixo reaplica o
`set_config` toda vez que uma transação nova começa nesta sessão, garantindo
que ele sempre roda ANTES de qualquer query do request dentro dessa
transação (é assim que o SQLAlchemy dispara o evento: depois do BEGIN físico,
antes do primeiro statement do chamador).
"""
import uuid
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import event, text
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

    Use esta dependência (em vez de `get_db`, que NÃO seta tenant — ver
    `app/core/db.py::get_db`) em qualquer rota que leia/escreva dados
    pertencentes a um tenant.
    """
    db = SessionLocal()
    tenant_id = str(current_user.tenant_id)

    # `SET app.tenant_id = :param` não é aceito pelo driver (SET não suporta
    # bind parameters — gera "syntax error at or near $1"). `set_config` é a
    # forma correta de setar uma GUC com parâmetro via prepared statement.
    # `true` = escopo de transação; ver docstring do módulo para o porquê.
    def _set_tenant_on_begin(session: Session, transaction, connection) -> None:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )

    event.listen(db, "after_begin", _set_tenant_on_begin)
    try:
        yield db
    finally:
        event.remove(db, "after_begin", _set_tenant_on_begin)
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
