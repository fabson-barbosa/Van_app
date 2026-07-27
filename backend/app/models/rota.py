"""Rota e Parada — hierarquia Tenant → Rotas → Paradas (arquitetura.md, 1.1 e 5).

`geo` usa PostGIS (POINT, SRID 4326 = WGS84/GPS) — motor de ETA depende disso.

`Parada.duracao_estimada_segundos` (Bloco B3, CLAUDE.md §5) é a "estimativa do
motorista" — semente do trajeto que TERMINA nesta parada, preenchida no
cadastro da rota. Nula até alguém informar; `app/services/leg_duration.py`
trata `None` como 240s (4min) por convenção, e só usa a semente enquanto o
bucket real (`leg_durations`, chave `rota_id, ordem`) não tiver nenhuma
amostra — a primeira amostra real já domina o EWMA (ver docstring do serviço).
"""
import uuid

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Rota(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "rotas"

    nome: Mapped[str] = mapped_column(nullable=False)
    turno: Mapped[str] = mapped_column(nullable=False)  # ex.: "manha", "tarde"
    escola: Mapped[str | None] = mapped_column(nullable=True)
    ativa: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Rota {self.nome} ({self.turno})>"


class Parada(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "paradas"

    rota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rotas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nome: Mapped[str | None] = mapped_column(nullable=True)
    endereco: Mapped[str | None] = mapped_column(nullable=True)
    ordem_base: Mapped[int] = mapped_column(nullable=False)
    geo = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    duracao_estimada_segundos: Mapped[int | None] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Parada {self.nome or self.id} (ordem {self.ordem_base})>"
