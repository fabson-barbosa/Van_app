"""TripStudent — estado do aluno dentro de uma viagem (CLAUDE.md §4).

Máquina de estados:
    aguardando -> chegou -> a_bordo -> entregue
                    (chegou) -> ausente

Este é o *projection* de estado atual (mutável); o log imutável de cada
transição vive em `EventoAluno` (models/evento_aluno.py) — a separação é
deliberada: aqui é rápido de consultar pra tela do motorista, lá é a fonte de
verdade auditável.

`ordem` é específico desta viagem (não `Parada.ordem_base`) porque reordenar
paradas é permitido antes do Cheguei (regra §8) sem afetar o "gabarito" da
rota. `parada_id` é um snapshot do ponto de embarque no momento em que a
viagem foi montada — se o endereço do aluno mudar depois, o histórico desta
viagem não deve mudar retroativamente.
"""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TripStudentEstado(str, enum.Enum):
    AGUARDANDO = "aguardando"
    CHEGOU = "chegou"
    A_BORDO = "a_bordo"
    ENTREGUE = "entregue"
    AUSENTE = "ausente"


class TripStudent(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "trip_students"
    __table_args__ = (UniqueConstraint("viagem_id", "aluno_id", name="uq_trip_students_viagem_aluno"),)

    viagem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("viagens.id", ondelete="CASCADE"), index=True, nullable=False
    )
    aluno_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alunos.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    parada_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paradas.id", ondelete="RESTRICT"), nullable=True
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[TripStudentEstado] = mapped_column(
        Enum(
            TripStudentEstado,
            name="trip_student_estado",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=TripStudentEstado.AGUARDANDO,
        nullable=False,
    )
    chegou_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkin_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ausente_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Espelha `checkin_em`, mas em relógio de SERVIDOR (quando o Checkin foi
    # recebido, não o instante reconciliado). Bloco B4 — é contra esta coluna,
    # nunca contra `checkin_em`, que a janela de 60s do desfazer-checkin é
    # medida: ambos os lados da comparação precisam ser imunes ao
    # `device_timestamp`/`device_enviado_em` que o cliente controla (ver
    # `app/services/trip_state_machine.py::desfazer_checkin`).
    checkin_registrado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TripStudent viagem={self.viagem_id} aluno={self.aluno_id} ({self.estado})>"
