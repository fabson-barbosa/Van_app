"""schema inicial — tabelas-núcleo + RLS por tenant_id

Cria as tabelas-núcleo descritas em docs/planejamento/arquitetura.md (seção 5)
necessárias para o Sprint 1 (cadastros e multi-tenancy): tenants, users,
veiculos, rotas, paradas, alunos, responsaveis.

Também habilita Row-Level Security (RLS) em toda tabela com `tenant_id`,
filtrando pela variável de sessão `app.tenant_id` — a aplicação deve fazer
`SET app.tenant_id = '<uuid-do-tenant>'` no início de cada transação/request
(ver arquitetura.md, 1.1: "iniciar com tenant_id + RLS no PostgreSQL").

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tabelas que carregam tenant_id e recebem política de RLS "fail-closed" via
# `app.tenant_id`.
#
# IMPORTANTE — `users` foi deixada de fora deliberadamente: o login precisa
# localizar o usuário pelo e-mail ANTES de sabermos o tenant_id (problema do
# ovo e da galinha — não dá pra fazer `SET app.tenant_id` sem antes saber quem
# é o usuário). Forçar RLS em `users` quebraria o fluxo de autenticação.
#
# Alternativas corretas para destravar isso com RLS completo (avaliar no
# Sprint 6 — hardening/LGPD):
#   1. Função SQL `SECURITY DEFINER` para o lookup de login (roda como dono da
#      tabela, ignora RLS, expõe só as colunas necessárias para autenticação);
#   2. Role de aplicação dedicada com BYPASSRLS apenas para o serviço de auth.
# Por ora, o controle de acesso a `users` é feito na camada de API (claims do
# JWT + `require_role`, ver app/api/deps.py).
TENANT_SCOPED_TABLES = ["veiculos", "rotas", "alunos"]


def upgrade() -> None:
    # Extensões necessárias: PostGIS (geoespacial) e pgcrypto (gen_random_uuid)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    user_role = postgresql.ENUM(
        "admin", "motorista", "motorista_backup", "responsavel",
        name="user_role",
    )
    user_role.create(op.get_bind(), checkfirst=True)

    # Referência usada na coluna abaixo: `create_type=False` evita que o
    # SQLAlchemy tente recriar o tipo ao criar a tabela `users` (geraria
    # "type user_role already exists" e faria todo o `upgrade()` reverter,
    # já que roda em uma única transação).
    user_role_col = postgresql.ENUM(
        "admin", "motorista", "motorista_backup", "responsavel",
        name="user_role",
        create_type=False,
    )

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("plano", sa.String(), nullable=False, server_default="free"),
        sa.Column("status_billing", sa.String(), nullable=False, server_default="trial"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, index=True),
        sa.Column("senha_hash", sa.String(), nullable=False),
        sa.Column("role", user_role_col, nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "veiculos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("placa", sa.String(), nullable=False, index=True),
        sa.Column("modelo", sa.String(), nullable=True),
        sa.Column("capacidade", sa.Integer(), nullable=True),
        sa.Column("km_atual", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("turno", sa.String(), nullable=False),
        sa.Column("escola", sa.String(), nullable=True),
        sa.Column("ativa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "paradas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("rota_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("rotas.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nome", sa.String(), nullable=True),
        sa.Column("endereco", sa.String(), nullable=True),
        sa.Column("ordem_base", sa.Integer(), nullable=False),
        sa.Column("geo", geoalchemy2.Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "alunos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("parada_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("paradas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("dados_medicos", sa.String(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "responsaveis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aluno_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alunos.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("parentesco", sa.String(), nullable=True),
        sa.Column("permissoes", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Row-Level Security: isolamento entre tenants ---
    # A aplicação deve executar `SET app.tenant_id = '<uuid>'` por sessão/request.
    # `current_setting(..., true)` retorna NULL se não setado, e a comparação com
    # NULL é sempre falsa — ou seja, sem tenant_id setado, nenhuma linha é visível
    # (fail-closed, mais seguro do que fail-open).
    for table in TENANT_SCOPED_TABLES:
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
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")

    op.drop_table("responsaveis")
    op.drop_table("alunos")
    op.drop_table("paradas")
    op.drop_table("rotas")
    op.drop_table("veiculos")
    op.drop_table("users")
    op.drop_table("tenants")

    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
