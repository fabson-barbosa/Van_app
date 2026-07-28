"""revisão de segurança — soft-delete (§7.5/A3) e auditoria de reatribuição (§11)

Duas coisas nesta migration, ambas saídas da revisão de segurança pós-B5:

1. **Soft-delete (achado A3 / regra inviolável §7.5).** `responsaveis` e
   `paradas` ganham `ativo` (NOT NULL, default true). `alunos.ativo` e
   `rotas.ativa` já existiam desde o B1 — essas duas tabelas não tinham a
   coluna, e os endpoints de DELETE faziam hard-delete de dado pessoal, o que
   contraria §7.5 ("nenhum dado pode ser hard-deleted até o B6"). Agora todos
   os `remover_*` fazem soft-delete.

2. **Auditoria de reatribuição de condutor (§11).** Tabela
   `viagem_reatribuicoes` registra cada troca de `viagem.motorista_id` — o
   `motorista_backup` assumindo a viagem de outro, ou o admin realocando. RLS
   fail-closed com o guard `NULLIF` (padrão 0006+) e trigger de imutabilidade
   append-only (mesma filosofia de `eventos_aluno`, §7.4).

Revision ID: 0010_soft_delete_e_reatribuicao
Revises: 0009_device_tokens
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0010_soft_delete_e_reatribuicao"
down_revision: Union[str, None] = "0009_device_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "viagem_reatribuicoes"
_TENANT_POLICY_EXPR = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    # --- (1) soft-delete: coluna `ativo` onde ainda não existia ---
    # server_default=true faz o backfill das linhas existentes num passo só.
    op.add_column("responsaveis", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("paradas", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))

    # --- (2) auditoria de reatribuição ---
    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("viagem_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("motorista_anterior_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("motoristas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("motorista_novo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("motoristas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reatribuido_por_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.execute(f"ALTER TABLE {_TABLE} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {_TABLE} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{_TABLE} ON {_TABLE}
        USING ({_TENANT_POLICY_EXPR})
        WITH CHECK ({_TENANT_POLICY_EXPR})
        """
    )

    # Append-only (§7.4, mesma filosofia do trigger de eventos_aluno em 0004).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_update_delete_viagem_reatribuicoes()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'viagem_reatribuicoes é append-only: % não é permitido (id=%)', TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_viagem_reatribuicoes_immutable
        BEFORE UPDATE OR DELETE ON viagem_reatribuicoes
        FOR EACH ROW EXECUTE FUNCTION forbid_update_delete_viagem_reatribuicoes();
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TRIGGER IF EXISTS trg_viagem_reatribuicoes_immutable ON {_TABLE}")
    op.execute("DROP FUNCTION IF EXISTS forbid_update_delete_viagem_reatribuicoes()")
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TABLE} ON {_TABLE}")
    op.drop_table(_TABLE)

    op.drop_column("paradas", "ativo")
    op.drop_column("responsaveis", "ativo")
