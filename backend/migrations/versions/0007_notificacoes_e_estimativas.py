"""bloco B3 — agendador de notificações, semente de leg_duration, atraso manual

Cria `notificacoes_agendadas` (CLAUDE.md §5 — cascata de notificações): estado
persistido (agendado/enviado/cancelado) em vez de sleep em memória, e um
índice único PARCIAL (`WHERE estado = 'agendado'`) em
`(trip_student_id, destinatario_user_id, tipo)` — é o que garante que
reagendar é sempre um UPDATE na linha existente, nunca uma segunda linha
pendente para o mesmo (aluno-na-viagem, destinatário, tipo). RLS fail-closed
no mesmo padrão das migrations 0004/0006 (`NULLIF(..., '')` — ver 0006 para o
porquê da blindagem contra GUC vazia).

Também adiciona:
- `paradas.duracao_estimada_segundos`: semente do trajeto (estimativa do
  motorista, CLAUDE.md §5) — nullable, preenchida no cadastro da rota.
- `viagens.atraso_manual_segundos`: acumulado do botão "Estou atrasado" —
  distinto de `atraso_acumulado_segundos` (já existe desde 0004, é só
  diagnóstico/exibição). Ver docstring de `app/models/viagem.py`.

Revision ID: 0007_notificacoes_e_estimativas
Revises: 0006_rls_guard_empty_tenant_guc
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007_notificacoes_e_estimativas"
down_revision: Union[str, None] = "0006_rls_guard_empty_tenant_guc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "notificacoes_agendadas"
_TENANT_POLICY_EXPR = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    # --- colunas novas em tabelas existentes ---
    op.add_column("paradas", sa.Column("duracao_estimada_segundos", sa.Integer(), nullable=True))
    op.add_column(
        "viagens",
        sa.Column("atraso_manual_segundos", sa.Integer(), nullable=False, server_default="0"),
    )

    # --- notificacoes_agendadas ---
    notificacao_tipo = postgresql.ENUM(
        "chegada", "iminencia", "preparo", name="notificacao_tipo",
    )
    notificacao_tipo.create(op.get_bind(), checkfirst=True)
    notificacao_tipo_col = postgresql.ENUM(
        "chegada", "iminencia", "preparo", name="notificacao_tipo", create_type=False,
    )

    notificacao_estado = postgresql.ENUM(
        "agendado", "enviado", "cancelado", name="notificacao_estado",
    )
    notificacao_estado.create(op.get_bind(), checkfirst=True)
    notificacao_estado_col = postgresql.ENUM(
        "agendado", "enviado", "cancelado", name="notificacao_estado", create_type=False,
    )

    op.create_table(
        _TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("viagem_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("trip_student_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("trip_students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("destinatario_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tipo", notificacao_tipo_col, nullable=False),
        sa.Column("estado", notificacao_estado_col, nullable=False, server_default="agendado"),
        sa.Column("agendado_para", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_cancelamento", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Idempotência do agendador: no máximo um agendamento PENDENTE por
    # (aluno-na-viagem, destinatário, tipo). Índice parcial — uma vez
    # enviado/cancelado, a linha sai do conjunto e não bloqueia um novo ciclo.
    op.create_index(
        "uq_notificacoes_pendentes_por_destinatario",
        _TABLE,
        ["trip_student_id", "destinatario_user_id", "tipo"],
        unique=True,
        postgresql_where=sa.text("estado = 'agendado'"),
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


def downgrade() -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{_TABLE} ON {_TABLE}")
    op.drop_index("uq_notificacoes_pendentes_por_destinatario", table_name=_TABLE)
    op.drop_table(_TABLE)
    postgresql.ENUM(name="notificacao_estado").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="notificacao_tipo").drop(op.get_bind(), checkfirst=True)

    op.drop_column("viagens", "atraso_manual_segundos")
    op.drop_column("paradas", "duracao_estimada_segundos")
