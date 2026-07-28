"""Aluno e Responsável (arquitetura.md, 3.5/3.6 — minimização de dados e LGPD).

`dados_medicos` guarda só o essencial (alergias/condições críticas) e deve ser
cifrado em repouso — a estratégia de criptografia entra no Sprint 6 (hardening/LGPD).
Por ora o campo existe como texto; a camada de cifragem será adicionada antes de
qualquer dado real trafegar.

Múltiplos responsáveis por aluno (N:1 responsável→aluno por linha, conforme o
modelo de dados da arquitetura) — cada um com permissões próprias.
"""
import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Aluno(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "alunos"

    nome: Mapped[str] = mapped_column(nullable=False)
    parada_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paradas.id", ondelete="SET NULL"), nullable=True
    )
    dados_medicos: Mapped[str | None] = mapped_column(nullable=True)
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Aluno {self.nome}>"


class CanalNotificacao(str, enum.Enum):
    """Canal de entrega da cascata de notificações (piloto WhatsApp via Twilio
    Sandbox — CLAUDE.md não cobre isso, decisão de produto registrada em
    PROGRESSO.md/ARQUITETURA.md). `AMBOS` dispara os dois; nenhum dos dois
    quebra o processamento dos demais responsáveis (ver
    `app/services/canal_router.py`)."""

    PUSH = "push"
    WHATSAPP = "whatsapp"
    AMBOS = "ambos"


class Responsavel(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "responsaveis"

    aluno_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alunos.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    parentesco: Mapped[str | None] = mapped_column(nullable=True)  # mãe, pai, avó...
    permissoes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # E.164 (+5516...), validado no Pydantic (app/schemas/cadastros.py) — nem
    # todo responsável cadastra na hora, por isso nullable.
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    canal_notificacao: Mapped[CanalNotificacao] = mapped_column(
        Enum(
            CanalNotificacao, name="canal_notificacao",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=CanalNotificacao.PUSH,
        nullable=False,
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Responsavel user={self.user_id} aluno={self.aluno_id}>"
