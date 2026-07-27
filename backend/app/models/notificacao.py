"""NotificacaoAgendada — agendamento/cascata de notificações (CLAUDE.md §5, Bloco B3).

Cobre os 3 tipos da cascata:
- `chegada`/`iminencia`: imediatas (CLAUDE.md §6 — "push sai imediatamente após
  confirmar, sem delay cancelável"). Nascem com `agendado_para=now()` e são
  marcadas `enviado` na mesma transação do evento — passam pela tabela só por
  uniformidade de auditoria, não têm janela de cancelamento na prática.
- `preparo`: agendada de verdade (Checkin(N) agenda para N+2, "faltam ~X min").
  É a única que precisa sobreviver entre requests e ser cancelável — por isso
  o índice único parcial abaixo e o estado persistido (nunca sleep em memória).

Idempotência: o índice único parcial `WHERE estado = 'agendado'` em
`(trip_student_id, destinatario_user_id, tipo)` garante no máximo UM
agendamento pendente por (aluno-na-viagem, destinatário, tipo). Reagendar é um
UPDATE no `agendado_para` da linha existente, não uma nova linha — os gatilhos
de cancelamento (desfazer checkin, ausente, reordenar, "estou atrasado",
recálculo da cauda) todos passam por essa mesma linha.

`payload` guarda dado ESTRUTURADO (ex.: faixa de minutos), não texto pronto —
a redação da mensagem (i18n, tom) é do app cliente (B4/B5, fora de escopo
desta rodada). O que o backend garante é o "quando" e o "nunca minuto exato".
"""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class NotificacaoTipo(str, enum.Enum):
    CHEGADA = "chegada"
    IMINENCIA = "iminencia"
    PREPARO = "preparo"


class NotificacaoEstado(str, enum.Enum):
    AGENDADO = "agendado"
    ENVIADO = "enviado"
    CANCELADO = "cancelado"


class NotificacaoAgendada(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "notificacoes_agendadas"
    __table_args__ = (
        Index(
            "uq_notificacoes_pendentes_por_destinatario",
            "trip_student_id", "destinatario_user_id", "tipo",
            unique=True,
            postgresql_where=text("estado = 'agendado'"),
        ),
    )

    viagem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("viagens.id", ondelete="CASCADE"), index=True, nullable=False
    )
    trip_student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trip_students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    destinatario_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tipo: Mapped[NotificacaoTipo] = mapped_column(
        Enum(NotificacaoTipo, name="notificacao_tipo", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    estado: Mapped[NotificacaoEstado] = mapped_column(
        Enum(
            NotificacaoEstado, name="notificacao_estado",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=NotificacaoEstado.AGENDADO,
        nullable=False,
    )
    agendado_para: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enviado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    motivo_cancelamento: Mapped[str | None] = mapped_column(nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<NotificacaoAgendada {self.tipo} trip_student={self.trip_student_id} ({self.estado})>"
