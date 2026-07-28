"""Registro de token de push (Bloco B5, CLAUDE.md §5/§6).

Qualquer papel autenticado pode registrar/remover o PRÓPRIO token — não há
dado de outro usuário envolvido, então não há minimização de dados a
proteger aqui (diferente de `api/responsavel.py`).

Upsert por `token` (índice único global — migration `0009_device_tokens`):
um aparelho compartilhado que troca de usuário reatribui a mesma linha, sem
acumular tokens mortos. O caso raro de um `token` já pertencer a OUTRO
tenant (RLS o torna invisível para esta sessão) vira 409 em vez de tentar
uma escrita cross-tenant — nunca contorna o filtro de tenant.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_tenant_db
from app.models.device_token import DeviceToken
from app.schemas.auth import CurrentUser
from app.schemas.dispositivos import DeviceTokenRegistrar, DeviceTokenRemover

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])

_TOKEN_DE_OUTRO_TENANT = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Este token já está registrado para outro operador.",
)


@router.post("/token", status_code=status.HTTP_204_NO_CONTENT)
def registrar_token(
    payload: DeviceTokenRegistrar,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    existente = db.scalars(select(DeviceToken).where(DeviceToken.token == payload.token)).first()
    if existente is not None:
        existente.user_id = user.id
        existente.provider = payload.provider
        existente.ativo = True
        existente.desativado_em = None
        db.commit()
        return

    db.add(DeviceToken(tenant_id=user.tenant_id, user_id=user.id, token=payload.token, provider=payload.provider))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _TOKEN_DE_OUTRO_TENANT from exc


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT)
def remover_token(
    payload: DeviceTokenRemover,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    """Chamado no logout — evita push para uma sessão que o usuário já encerrou
    neste aparelho. Não é erro remover um token que já não existe/não é seu."""
    existente = db.scalars(
        select(DeviceToken).where(DeviceToken.token == payload.token, DeviceToken.user_id == user.id)
    ).first()
    if existente is not None:
        db.delete(existente)
        db.commit()
