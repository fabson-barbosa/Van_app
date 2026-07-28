"""WhatsApp via Twilio Sandbox — canal de notificação por responsável

Piloto para reduzir a fricção de instalar app no celular (CLAUDE.md não
cobre WhatsApp — decisão de produto tomada fora do domínio original,
registrada em PROGRESSO.md/ARQUITETURA.md).

Adiciona em `responsaveis` (mesma tabela de `permissoes.receber_notificacoes`,
é o cadastro por vínculo aluno×responsável):
- `telefone`: E.164 (`+5516...`), nullable — nem todo responsável cadastra na
  hora. Validado no Pydantic (`app/schemas/cadastros.py`), não no banco.
- `canal_notificacao`: enum `push`/`whatsapp`/`ambos`, NOT NULL,
  `server_default='push'` — todo responsável já cadastrado continua só no
  push, comportamento inalterado até alguém trocar explicitamente.

Revision ID: 0010_canal_notificacao_responsavel
Revises: 0009_device_tokens
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_canal_notificacao_responsavel"
down_revision: Union[str, None] = "0009_device_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "responsaveis"


def upgrade() -> None:
    canal = postgresql.ENUM("push", "whatsapp", "ambos", name="canal_notificacao")
    canal.create(op.get_bind(), checkfirst=True)
    canal_col = postgresql.ENUM("push", "whatsapp", "ambos", name="canal_notificacao", create_type=False)

    op.add_column(_TABLE, sa.Column("telefone", sa.String(length=20), nullable=True))
    op.add_column(
        _TABLE,
        sa.Column("canal_notificacao", canal_col, nullable=False, server_default="push"),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "canal_notificacao")
    op.drop_column(_TABLE, "telefone")
    postgresql.ENUM(name="canal_notificacao").drop(op.get_bind(), checkfirst=True)
