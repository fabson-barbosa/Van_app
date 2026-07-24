"""Schemas Pydantic do fluxo de autenticação."""
import uuid

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUser(BaseModel):
    """Representação do usuário autenticado, derivada das claims do JWT."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: EmailStr
    role: UserRole

    model_config = {"from_attributes": True}
