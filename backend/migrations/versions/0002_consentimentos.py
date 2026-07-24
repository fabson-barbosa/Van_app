"""consentimentos — onboarding do tenant (aceite do DPA/LGPD)

Adiciona a tabela `consentimentos` (Sprint 1 — cadastros e multi-tenancy),
usada para registrar o aceite do Data Processing Agreement por um admin do
tenant. Carrega `tenant_id` (via `TenantMixin`), então entra na lista de
tabelas com RLS fail-closed por `app.tenant_id` — mesmo padrão da migration
0001 (ver `TENANT_SCOPED_TABLES` lá).

Revision ID: 0002_consentimentos
Revises: 0001_initial_schema
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_consentimentos"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "consentimentos"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tipo", sa.String(length=50), nullable=False, server_default="dpa"),
        sa.Column("versao", sa.String(length=20), nullable=False),
        sa.Column("aceito_por_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Row-Level Security: mesmo padrão fail-closed da migration 0001 ---
    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_TABLE} ON {_TABLE}
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TABLE} ON {_TABLE}")
    op.drop_table(_TABLE)
