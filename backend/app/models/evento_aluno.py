"""EventoAluno — trilha de auditoria append-only da máquina de estados (CLAUDE.md §4, regra 7.4).

Grava `timestamp` (servidor) e `device_timestamp` (cliente) para reconciliar
eventos registrados offline pelo app do Motorista (§4, §8). Imutabilidade não
é só convenção de código: a migration que cria esta tabela adiciona um
trigger de banco que bloqueia UPDATE/DELETE — a mesma filosofia do RLS
("não pode depender da camada de aplicação").

`estado_anterior` (Bloco B2) registra de onde veio a transição. Isso é o que
distingue, sem ambiguidade, um `ausente` direto de `aguardando` (aluno pulado,
nunca chegou a `chegou` — sem dwell, não vira amostra de `leg_duration`) de um
`ausente` vindo de `chegou`. `timestamp` é atribuído pela aplicação no momento
em que o evento é processado (não pelo `server_default`, que é só uma rede de
segurança) — assim a máquina de estados em `services/` permanece pura e
testável sem banco (recebe o relógio como parâmetro).
"""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, UUIDPrimaryKeyMixin
from app.models.trip_student import TripStudentEstado


class EventoAlunoTipo(str, enum.Enum):
    CHEGUEI = "cheguei"
    CHECKIN = "checkin"
    CHECKOUT = "checkout"
    AUSENTE = "ausente"
    DESFAZER_CHEGADA = "desfazer_chegada"
    DESFAZER_CHECKIN = "desfazer_checkin"


class EventoAluno(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "eventos_aluno"

    trip_student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tipo: Mapped[EventoAlunoTipo] = mapped_column(
        Enum(
            EventoAlunoTipo,
            name="evento_aluno_tipo",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    estado_anterior: Mapped[TripStudentEstado | None] = mapped_column(
        Enum(
            TripStudentEstado,
            name="trip_student_estado",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
            create_type=False,
        ),
        nullable=True,
    )
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    device_timestamp: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registrado_por_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventoAluno {self.tipo} trip_student={self.trip_student_id}>"
