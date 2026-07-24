"""User - RBAC (arquitetura.md, 3.5): Admin, Motorista, Motorista Backup, Responsavel."""
import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MOTORISTA = "motorista"
    MOTORISTA_BACKUP = "motorista_backup"
    RESPONSAVEL = "responsavel"


class User(Base, UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin):
    __tablename__ = "users"

    nome: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    senha_hash: Mapped[str] = mapped_column(nullable=False)
    # `values_callable` e necessario porque o tipo `user_role` no Postgres foi
    # criado com os valores em minusculas (migration 0001: "admin", "motorista",
    # ...). Sem isso, o SQLAlchemy grava o *nome* do membro do enum Python
    # ("ADMIN") em vez do seu `.value` ("admin"), e o INSERT falha com
    # "invalid input value for enum user_role".
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    ativo: Mapped[bool] = mapped_column(default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} ({self.role})>"
