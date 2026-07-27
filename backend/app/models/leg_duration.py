"""LegDuration — média móvel de trajeto por (rota, ordem, faixa horária, dia da semana).

Formato exato citado no CLAUDE.md §5: `leg_duration(rota_id, ordem,
faixa_horaria, dia_semana, segundos, amostras)`. A semente inicial (estimativa
do motorista) e a lógica de atualização da média móvel são do Bloco B3 — aqui
só existe a tabela.

Convenções (não especificadas no CLAUDE.md, definidas aqui para B1):
- `ordem`: identifica o trecho que TERMINA na parada de mesma ordem dentro da
  rota (trajeto até a parada `ordem`), espelhando `TripStudent.ordem`.
- `dia_semana`: 0=segunda ... 6=domingo (`date.weekday()` do Python).
- `faixa_horaria`: hora cheia de início do bucket, 0-23 (ex.: viagem que
  começou às 6h42 cai no bucket 6).
"""
import uuid

from sqlalchemy import Float, ForeignKey, Integer, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class LegDuration(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "leg_durations"
    __table_args__ = (
        UniqueConstraint(
            "rota_id", "ordem", "dia_semana", "faixa_horaria", name="uq_leg_durations_bucket"
        ),
    )

    rota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rotas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    dia_semana: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    faixa_horaria: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    segundos_media: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    amostras: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LegDuration rota={self.rota_id} ordem={self.ordem} dia={self.dia_semana} faixa={self.faixa_horaria}h>"
