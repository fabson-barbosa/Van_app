"""fecha lacuna de RLS em paradas e responsaveis

`paradas` e `responsaveis` nasceram sem `tenant_id` (isolamento dependia de
join manual com `rotas`/`alunos` na aplicação). Isso contraria a decisão de
arquitetura do CLAUDE.md ("isolamento não pode depender da camada de
aplicação") e a regra inviolável 7.3 ("RLS ativa em toda tabela com
tenant_id"). Bloco B1 lista `parada` e `responsavel` como modelos em escopo,
então fechamos a lacuna aqui: adiciona `tenant_id` (backfill a partir da
tabela pai), NOT NULL, e a mesma política fail-closed das demais tabelas.

Revision ID: 0003_rls_paradas_responsaveis
Revises: 0002_consentimentos
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_rls_paradas_responsaveis"
down_revision: Union[str, None] = "0002_consentimentos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEWLY_SCOPED_TABLES = ["paradas", "responsaveis"]


def upgrade() -> None:
    # --- paradas: tenant_id vem de rotas.tenant_id ---
    op.add_column("paradas", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE paradas
        SET tenant_id = rotas.tenant_id
        FROM rotas
        WHERE paradas.rota_id = rotas.id
        """
    )
    op.alter_column("paradas", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_paradas_tenant_id_tenants", "paradas", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_paradas_tenant_id", "paradas", ["tenant_id"])

    # --- responsaveis: tenant_id vem de alunos.tenant_id ---
    op.add_column("responsaveis", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        """
        UPDATE responsaveis
        SET tenant_id = alunos.tenant_id
        FROM alunos
        WHERE responsaveis.aluno_id = alunos.id
        """
    )
    op.alter_column("responsaveis", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_responsaveis_tenant_id_tenants", "responsaveis", "tenants", ["tenant_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_responsaveis_tenant_id", "responsaveis", ["tenant_id"])

    for table in _NEWLY_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
            """
        )


def downgrade() -> None:
    for table in _NEWLY_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_index("ix_responsaveis_tenant_id", table_name="responsaveis")
    op.drop_constraint("fk_responsaveis_tenant_id_tenants", "responsaveis", type_="foreignkey")
    op.drop_column("responsaveis", "tenant_id")

    op.drop_index("ix_paradas_tenant_id", table_name="paradas")
    op.drop_constraint("fk_paradas_tenant_id_tenants", "paradas", type_="foreignkey")
    op.drop_column("paradas", "tenant_id")
