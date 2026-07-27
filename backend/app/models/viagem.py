"""Viagem — uma execução concreta de uma Rota em uma data (CLAUDE.md §4/§5).

A máquina de estados por aluno vive em `TripStudent` (models/trip_student.py);
`Viagem` só carrega o estado grosso do turno inteiro (planejada/em andamento/
finalizada) mais os agregados do motor de tempos (`atraso_acumulado_segundos`)
e o flag da varredura final bloqueante (regra inviolável 7.1 — a lógica que
impede finalizar com aluno em estado não-terminal é do Bloco B2; aqui só existe
a coluna).

`rota_id`/`veiculo_id`/`motorista_id` usam `ondelete=RESTRICT`: viagem é
registro de auditoria (regra inviolável 7.4 por associação), não pode sumir
porque alguém apagou o veículo ou o motorista.
"""
import datetime
import enum
import uuid

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ViagemStatus(str, enum.Enum):
    PLANEJADA = "planejada"
    EM_ANDAMENTO = "em_andamento"
    FINALIZADA = "finalizada"


class Viagem(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "viagens"

    rota_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rotas.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    veiculo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("veiculos.id", ondelete="RESTRICT"), nullable=False
    )
    motorista_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("motoristas.id", ondelete="RESTRICT"), nullable=False
    )
    data: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[ViagemStatus] = mapped_column(
        Enum(ViagemStatus, name="viagem_status", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        default=ViagemStatus.PLANEJADA,
        nullable=False,
    )
    iniciada_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finalizada_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    atraso_acumulado_segundos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    varredura_confirmada: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Viagem rota={self.rota_id} data={self.data} ({self.status})>"
