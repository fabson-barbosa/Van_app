"""EventoAluno — trilha de auditoria append-only da máquina de estados (CLAUDE.md §4, regra 7.4).

Três relógios, três papéis (Bloco B4, migration `0008_reconciliacao_temporal` —
fecha a lacuna de `ARQUITETURA.md` §8):

- `ocorrido_em`: instante RECONCILIADO em que o evento realmente aconteceu no
  aparelho (`device_timestamp` + offset contra o relógio do servidor, ver
  `app/services/reconciliacao.py`). É deste campo que saem `chegou_em`/
  `checkin_em`/etc — o motor de tempos do B3 precisa dos intervalos reais,
  não de quando o evento chegou ao servidor.
- `registrado_em`: quando o servidor recebeu o evento. Auditoria — e é contra
  ESTE campo, nunca contra o aparelho, que a janela de 60s do desfazer-checkin
  é medida (decisão de produto: medir contra o relógio do aparelho abriria
  undo infinito com relógio manipulado).
- `device_timestamp`: valor cru enviado pelo aparelho, sem nenhuma correção.
  Forense — o que o aparelho achava que era a hora, ponto.

`event_id` (Bloco B4) é a chave de idempotência da fila offline: gerado no
aparelho no momento do toque, reenviado sem trocar em cada tentativa. Um
reenvio com o mesmo `event_id` não grava um segundo evento (índice único) —
a API devolve o estado atual em vez de reprocessar.

Imutabilidade não é só convenção de código: a migration que cria esta tabela
adiciona um trigger de banco que bloqueia UPDATE/DELETE — a mesma filosofia
do RLS ("não pode depender da camada de aplicação").

`estado_anterior` (Bloco B2) registra de onde veio a transição. Isso é o que
distingue, sem ambiguidade, um `ausente` direto de `aguardando` (aluno pulado,
nunca chegou a `chegou` — sem dwell, não vira amostra de `leg_duration`) de um
`ausente` vindo de `chegou`. `ocorrido_em`/`registrado_em` são atribuídos pela
aplicação (não pelo `server_default`, que é só rede de segurança) — assim a
máquina de estados em `services/` permanece pura e testável sem banco (recebe
o relógio como parâmetro).
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
    ocorrido_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    registrado_em: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    device_timestamp: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    registrado_por_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<EventoAluno {self.tipo} trip_student={self.trip_student_id}>"
