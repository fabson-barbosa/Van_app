"""Registro de token de push (Bloco B5, CLAUDE.md §5/§6).

Qualquer papel autenticado pode registrar/remover o PRÓPRIO token — não há
dado de outro usuário envolvido, então não há minimização de dados a
proteger aqui (diferente de `api/responsavel.py`).

Upsert por `token` (índice único global — migration `0009_device_tokens`):
um aparelho compartilhado que troca de usuário reatribui a mesma linha, sem
acumular tokens mortos. O caso raro de um `token` já pertencer a OUTRO
tenant (RLS o torna invisível para esta sessão) vira 409 em vez de tentar
uma escrita cross-tenant — nunca contorna o filtro de tenant.

Achado A5 (revisão de segurança) — prova de posse do token: a reatribuição
para o chamador é DELIBERADA (é o fluxo de aparelho compartilhado: quem loga
naquele aparelho passa a receber os próprios pushes ali). A posse do token
Expo — que só é conhecido pelo aparelho que o gerou — É a prova implícita.
O risco residual (alguém que conheça o token opaco de outro reatribuí-lo para
si, redirecionando os próprios pushes para o aparelho da vítima) é
griefing/incômodo, não exfiltração: `user_id` sempre vira o do chamador, então
o atacante nunca RECEBE dado de ninguém. Cross-tenant continua barrado por RLS
(409). Sem atestação de dispositivo (fora do Expo Go) não há como fechar isso
no servidor — documentado, não silenciado.
"""
import datetime

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
    neste aparelho. Não é erro remover um token que já não existe/não é seu.

    Soft-delete (achado A3): desativa em vez de apagar — o `ExpoPushSender` já
    só consulta tokens `ativo=True` (`app/services/expo_push.py`), então o
    efeito prático (parar de enviar) é idêntico ao DELETE, sem hard-delete e
    reaproveitando a mesma linha se o aparelho voltar a logar."""
    existente = db.scalars(
        select(DeviceToken).where(DeviceToken.token == payload.token, DeviceToken.user_id == user.id)
    ).first()
    if existente is not None and existente.ativo:
        existente.ativo = False
        existente.desativado_em = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
