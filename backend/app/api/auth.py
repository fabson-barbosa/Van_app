"""Endpoints de autenticação.

Login simples por e-mail/senha (Sprint 0). Note que esta consulta usa `get_db`
puro (sem RLS) porque, neste momento, ainda não sabemos a qual tenant o
usuário pertence — é exatamente essa informação que o login resolve.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="E-mail ou senha inválidos.",
)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))

    if user is None or not user.ativo or not verify_password(payload.senha, user.senha_hash):
        raise _INVALID_CREDENTIALS

    token = create_access_token(
        subject=str(user.id),
        extra_claims={
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "role": user.role.value,
        },
    )
    return TokenResponse(access_token=token)
