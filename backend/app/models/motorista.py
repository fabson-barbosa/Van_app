"""Motorista — perfil de condutor vinculado a um User com role=motorista.

Mesmo padrão de `Responsavel` (models/aluno.py): o `User` cuida de
autenticação/RBAC, o perfil guarda os dados específicos do papel (CNH,
telefone). `Viagem.motorista_id` referencia esta tabela, não `users`
diretamente.
"""
import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Motorista(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "motoristas"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )
    cnh_numero: Mapped[str | None] = mapped_column(nullable=True)
    cnh_categoria: Mapped[str | None] = mapped_column(nullable=True)
    telefone: Mapped[str | None] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Motorista user={self.user_id}>"
