"""bloco B5 — device_tokens (registro de push do app Responsável)

Guarda o token de push por usuário para a cascata de notificações do B3
(`app/services/notificacoes.py`) ter para quem entregar de verdade — até
aqui só existia `StubFCMSender`. `provider` (`expo`/`fcm`) existe desde já
mesmo só usando `expo` nesta rodada: o app roda em Expo Go (SDK exato, sem
dev client custom — mesma restrição do B4), então o único caminho de push
viável é o Expo Push Service; guardar o provedor no schema deixa uma futura
migração para FCM direto ser troca de adaptador, não migration nova.

`ativo=false` (nunca DELETE) quando o Expo Push Service reporta
`DeviceNotRegistered` — ver `app/services/expo_push.py`. Índice único em
`token` (upsert por token, cobre aparelho compartilhado trocando de
usuário). RLS fail-closed com o guard `NULLIF` (mesmo padrão de 0006/0007 —
tabela nasce direto nesse padrão, não precisa de migration de correção
depois).

Revision ID: 0009_device_tokens
Revises: 0008_reconciliacao_temporal
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0009_device_tokens"
down_revision: Union[str, None] = "0008_reconciliacao_temporal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "device_tokens"
_TENANT_POLICY_EXPR = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    provider = postgresql.ENUM("expo", "fcm", name="device_token_provider")
    provider.create(op.get_bind(), checkfirst=True)
    provider_col = postgresql.ENUM("expo", "fcm", name="device_token_provider", create_type=False)

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("provider", provider_col, nullable=False, server_default="expo"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("desativado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_device_tokens_token", _TABLE, ["token"])

    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_TABLE} ON {_TABLE}
        USING ({_TENANT_POLICY_EXPR})
        WITH CHECK ({_TENANT_POLICY_EXPR})
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TABLE} ON {_TABLE}")
    op.drop_table(_TABLE)
    postgresql.ENUM(name="device_token_provider").drop(op.get_bind(), checkfirst=True)
