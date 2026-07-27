"""bloco B1 — motoristas, viagens, trip_students, eventos_aluno, leg_durations

Cria as tabelas do motor de viagem descritas no CLAUDE.md (§4 máquina de
estados, §5 motor de tempos, §9 bloco B1):

- `motoristas`: perfil de condutor vinculado a um `users.role=motorista`
  (mesmo padrão de `responsaveis`).
- `viagens`: uma execução concreta de uma rota numa data.
- `trip_students`: estado do aluno dentro de uma viagem (projeção mutável da
  máquina de estados; `ordem` própria da viagem, distinta de
  `paradas.ordem_base`, porque reordenar antes do Cheguei é permitido — §8).
- `eventos_aluno`: log append-only de cada transição (regra inviolável 7.4).
  Um trigger de banco bloqueia UPDATE/DELETE — imutabilidade não pode
  depender de disciplina da aplicação, mesma razão pela qual RLS é
  banco-nativo.
- `leg_durations`: média móvel de trajeto por (rota, ordem, dia_semana,
  faixa_horaria) — formato do §5.

Todas as tabelas carregam `tenant_id` e recebem a mesma política fail-closed
das migrations 0001-0003.

Revision ID: 0004_trip_domain
Revises: 0003_rls_paradas_responsaveis
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_trip_domain"
down_revision: Union[str, None] = "0003_rls_paradas_responsaveis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_SCOPED_TABLES = ["motoristas", "viagens", "trip_students", "eventos_aluno", "leg_durations"]


def _create_tenant_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation_{table} ON {table}
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def upgrade() -> None:
    # --- motoristas ---
    op.create_table(
        "motoristas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("cnh_numero", sa.String(), nullable=True),
        sa.Column("cnh_categoria", sa.String(), nullable=True),
        sa.Column("telefone", sa.String(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- viagens ---
    viagem_status = postgresql.ENUM(
        "planejada", "em_andamento", "finalizada", name="viagem_status",
    )
    viagem_status.create(op.get_bind(), checkfirst=True)
    viagem_status_col = postgresql.ENUM(
        "planejada", "em_andamento", "finalizada", name="viagem_status", create_type=False,
    )

    op.create_table(
        "viagens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rota_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rotas.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("veiculo_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("veiculos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("motorista_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("motoristas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("status", viagem_status_col, nullable=False, server_default="planejada"),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finalizada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("atraso_acumulado_segundos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("varredura_confirmada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_viagens_rota_id_data", "viagens", ["rota_id", "data"])

    # --- trip_students ---
    trip_student_estado = postgresql.ENUM(
        "aguardando", "chegou", "a_bordo", "entregue", "ausente", name="trip_student_estado",
    )
    trip_student_estado.create(op.get_bind(), checkfirst=True)
    trip_student_estado_col = postgresql.ENUM(
        "aguardando", "chegou", "a_bordo", "entregue", "ausente",
        name="trip_student_estado", create_type=False,
    )

    op.create_table(
        "trip_students",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("viagem_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("viagens.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("aluno_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alunos.id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("parada_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("paradas.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("estado", trip_student_estado_col, nullable=False, server_default="aguardando"),
        sa.Column("chegou_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkin_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkout_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ausente_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("viagem_id", "aluno_id", name="uq_trip_students_viagem_aluno"),
    )
    op.create_index("ix_trip_students_viagem_id_ordem", "trip_students", ["viagem_id", "ordem"])

    # --- eventos_aluno (append-only) ---
    evento_aluno_tipo = postgresql.ENUM(
        "cheguei", "checkin", "checkout", "ausente", "desfazer_chegada", name="evento_aluno_tipo",
    )
    evento_aluno_tipo.create(op.get_bind(), checkfirst=True)
    evento_aluno_tipo_col = postgresql.ENUM(
        "cheguei", "checkin", "checkout", "ausente", "desfazer_chegada",
        name="evento_aluno_tipo", create_type=False,
    )

    op.create_table(
        "eventos_aluno",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("trip_student_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("trip_students.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tipo", evento_aluno_tipo_col, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("device_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registrado_por_user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_eventos_aluno_trip_student_id_timestamp", "eventos_aluno", ["trip_student_id", "timestamp"])

    # Trigger de imutabilidade — regra inviolável 7.4 ("trilha de auditoria
    # imutável"), reforçada no banco em vez de depender do código da API só
    # nunca chamar UPDATE/DELETE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION forbid_update_delete_eventos_aluno()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'eventos_aluno é append-only: % não é permitido (id=%)', TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_eventos_aluno_immutable
        BEFORE UPDATE OR DELETE ON eventos_aluno
        FOR EACH ROW EXECUTE FUNCTION forbid_update_delete_eventos_aluno();
        """
    )

    # --- leg_durations ---
    op.create_table(
        "leg_durations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("rota_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rotas.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("dia_semana", sa.SmallInteger(), nullable=False),
        sa.Column("faixa_horaria", sa.SmallInteger(), nullable=False),
        sa.Column("segundos_media", sa.Float(), nullable=False, server_default="0"),
        sa.Column("amostras", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("rota_id", "ordem", "dia_semana", "faixa_horaria", name="uq_leg_durations_bucket"),
    )

    for table in _TENANT_SCOPED_TABLES:
        _create_tenant_policy(table)


def downgrade() -> None:
    for table in _TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")

    op.drop_table("leg_durations")

    op.execute("DROP TRIGGER IF EXISTS trg_eventos_aluno_immutable ON eventos_aluno")
    op.execute("DROP FUNCTION IF EXISTS forbid_update_delete_eventos_aluno()")
    op.drop_table("eventos_aluno")
    postgresql.ENUM(name="evento_aluno_tipo").drop(op.get_bind(), checkfirst=True)

    op.drop_table("trip_students")
    postgresql.ENUM(name="trip_student_estado").drop(op.get_bind(), checkfirst=True)

    op.drop_table("viagens")
    postgresql.ENUM(name="viagem_status").drop(op.get_bind(), checkfirst=True)

    op.drop_table("motoristas")
