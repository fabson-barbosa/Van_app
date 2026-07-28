"""ViagemReatribuicao — trilha de auditoria de troca de condutor da viagem.

CLAUDE.md §3/§11: `motorista_backup` existe para assumir uma viagem em
andamento quando o aparelho do motorista titular falha (mitigação do celular
como ponto único de falha). A troca de `viagem.motorista_id` é um fato
sensível — quem operou a viagem a partir de quando — então cada reatribuição
grava uma linha aqui.

Append-only por trigger de banco (mesma filosofia de `eventos_aluno`, regra
inviolável §7.4): a migration que cria a tabela bloqueia UPDATE/DELETE. A
imutabilidade não depende de disciplina da aplicação.
"""
import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, UUIDPrimaryKeyMixin


class ViagemReatribuicao(Base, UUIDPrimaryKeyMixin, TenantMixin):
    __tablename__ = "viagem_reatribuicoes"

    viagem_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("viagens.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # `motorista_anterior_id` é nullable só por robustez (viagem sempre tem
    # condutor no schema, mas a auditoria não deve quebrar se um dia não tiver).
    motorista_anterior_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("motoristas.id", ondelete="SET NULL"), nullable=True
    )
    motorista_novo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("motoristas.id", ondelete="RESTRICT"), nullable=False
    )
    reatribuido_por_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    motivo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ViagemReatribuicao viagem={self.viagem_id} novo={self.motorista_novo_id}>"
