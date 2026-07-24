"""Veículo — frota do tenant. Manutenções (Fase 3) ficam para depois."""
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Veiculo(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "veiculos"

    placa: Mapped[str] = mapped_column(nullable=False, index=True)
    modelo: Mapped[str | None] = mapped_column(nullable=True)
    capacidade: Mapped[int | None] = mapped_column(nullable=True)
    km_atual: Mapped[int] = mapped_column(default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Veiculo {self.placa}>"
