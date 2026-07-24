"""Consentimento — registro de aceite de termos/contratos por tenant (LGPD).

Cobre o "Onboarding do tenant: aceite do DPA (contrato de operador LGPD)" do
Sprint 1. Mantemos o histórico (não sobrescrevemos): cada aceite vira uma
linha nova, permitindo auditoria de quando e por quem cada versão foi aceita
(ver arquitetura.md — módulo de compliance / Sprint 6 trata o restante do
módulo de consentimentos para dados sensíveis).
"""
import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Consentimento(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "consentimentos"

    # "dpa" (contrato de operador LGPD) é o tipo usado no onboarding do Sprint 1;
    # outros tipos (ex.: "termos_uso", "consentimento_dados_sensiveis") entram
    # conforme o módulo de compliance evoluir (Sprint 6).
    tipo: Mapped[str] = mapped_column(String(50), nullable=False, default="dpa")
    versao: Mapped[str] = mapped_column(String(20), nullable=False)

    aceito_por_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Consentimento {self.tipo} v{self.versao} (tenant={self.tenant_id})>"
