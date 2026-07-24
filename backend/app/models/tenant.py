"""Tenant — transportador (de van autônoma MEI a empresa com frota).

Cada tenant é isolado via tenant_id + RLS no Postgres (arquitetura.md, 1.1).
"""
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    nome: Mapped[str] = mapped_column(nullable=False)
    plano: Mapped[str] = mapped_column(default="free", nullable=False)
    status_billing: Mapped[str] = mapped_column(default="trial", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tenant {self.nome} ({self.status_billing})>"
