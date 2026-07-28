"""DeviceToken — registro de token de push por usuário (Bloco B5, CLAUDE.md §5/§6).

`provider` existe desde o início mesmo só tendo um valor usado (`expo`) —
decisão do usuário: o app roda em Expo Go (SDK exato, sem dev client custom),
então o único caminho de push viável hoje é o Expo Push Service (que entrega
no Android via FCM por baixo). Guardar o provedor no schema deixa uma futura
migração para FCM/APNs direto (quando o app sair do Expo Go) uma troca de
adaptador (`app/services/expo_push.py` -> outro `FCMSender`), não uma
migration nova.

`ativo=False` (nunca DELETE) quando o Expo Push Service responde
`DeviceNotRegistered` para esse token — token morto acumulado sem essa
marcação é a causa clássica de push que "some" silenciosamente. Um mesmo
`token` só pode pertencer a um `user_id` por vez (upsert por token — cobre o
caso de aparelho compartilhado trocando de usuário).
"""
import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class DeviceTokenProvider(str, enum.Enum):
    EXPO = "expo"
    FCM = "fcm"


class DeviceToken(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_device_tokens_token"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[DeviceTokenProvider] = mapped_column(
        Enum(
            DeviceTokenProvider, name="device_token_provider",
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=DeviceTokenProvider.EXPO,
        nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)
    desativado_em: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DeviceToken user={self.user_id} provider={self.provider} ativo={self.ativo}>"
