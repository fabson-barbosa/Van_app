"""bloco B2 — desfazer checkin + estado_anterior em eventos_aluno

Suporte de schema para a máquina de estados do Bloco B2 (CLAUDE.md §4):

- Adiciona `desfazer_checkin` ao enum `evento_aluno_tipo` (transição
  `a_bordo -> chegou`, janela de 60s no servidor).
- Adiciona `eventos_aluno.estado_anterior` (reaproveita o enum
  `trip_student_estado` já existente) — registra de onde a transição veio,
  necessário para distinguir `ausente` direto de `aguardando` (pulado, sem
  dwell) de `ausente` vindo de `chegou`.

Revision ID: 0005_desfazer_checkin
Revises: 0004_trip_domain
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005_desfazer_checkin"
down_revision: Union[str, None] = "0004_trip_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE evento_aluno_tipo ADD VALUE IF NOT EXISTS 'desfazer_checkin'")

    trip_student_estado_col = postgresql.ENUM(
        "aguardando", "chegou", "a_bordo", "entregue", "ausente",
        name="trip_student_estado", create_type=False,
    )
    op.add_column(
        "eventos_aluno",
        sa.Column("estado_anterior", trip_student_estado_col, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("eventos_aluno", "estado_anterior")
    # Postgres não suporta DROP VALUE em enum — remover 'desfazer_checkin' do
    # tipo `evento_aluno_tipo` exigiria recriar o tipo inteiro. Não fazemos
    # isso aqui: downgrade deixa o valor extra no enum (inofensivo sem uso).
