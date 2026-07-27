"""bloco B2 (portão de validação) — blinda as políticas de RLS contra GUC vazia

Achado durante a validação em runtime do portão do CLAUDE.md §9 (Postgres real,
não `--sql` offline): `app/api/deps.py::get_tenant_db` usava
`set_config('app.tenant_id', <valor>, false)` — escopo de SESSÃO, não de
TRANSAÇÃO. Numa engine com pool de conexões, isso deixa o `app.tenant_id` de
um request "grudado" na conexão física depois do COMMIT, disponível para o
próximo request que reaproveitar essa conexão — viola o próprio comentário do
arquivo ("fail-closed, mais seguro que fail-open").

A correção (troca para `set_config(..., true)`, escopo de transação — feita
junto com este commit) tem um efeito colateral no Postgres que só aparece em
runtime: uma GUC placeholder (`app.tenant_id` não é declarada por nenhuma
extensão) que **nunca** foi tocada numa sessão retorna `NULL` via
`current_setting(nome, true)`. Mas depois de tocada ao menos uma vez — mesmo
com escopo local, mesmo já tendo sido resetada pelo fim da transação — o
valor de "reset" do Postgres para ela vira string vazia (`''`), não `NULL`.
Numa conexão pooled reaproveitada (o cenário normal depois da correção acima),
isso significa que `current_setting('app.tenant_id', true)::uuid` explode com
`invalid input syntax for type uuid: ""` em vez de simplesmente devolver zero
linhas — troca um vazamento silencioso por um erro 500, mas ainda não é o
fail-closed ("zero linhas, nunca todas") que a regra 7.3 do CLAUDE.md exige.

Fix: blindar o cast com `NULLIF(..., '')` em todas as políticas de RLS —
string vazia vira `NULL`, `tenant_id = NULL` é sempre `UNKNOWN`, a linha é
excluída sem erro. Cobre as 11 tabelas com `tenant_id` criadas nas migrations
0001-0004 (`tenants` e `users` ficam de fora deliberadamente — ver comentário
em 0001_initial_schema.py).

Revision ID: 0006_rls_guard_empty_tenant_guc
Revises: 0005_desfazer_checkin
Create Date: 2026-07-27
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_rls_guard_empty_tenant_guc"
down_revision: Union[str, None] = "0005_desfazer_checkin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TENANT_SCOPED_TABLES = [
    "veiculos", "rotas", "alunos",              # 0001
    "consentimentos",                           # 0002
    "paradas", "responsaveis",                  # 0003
    "motoristas", "viagens", "trip_students", "eventos_aluno", "leg_durations",  # 0004
]

_ORIGINAL_EXPR = "tenant_id = current_setting('app.tenant_id', true)::uuid"
_GUARDED_EXPR = "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    for table in _TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING ({_GUARDED_EXPR})
            WITH CHECK ({_GUARDED_EXPR})
            """
        )


def downgrade() -> None:
    for table in _TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING ({_ORIGINAL_EXPR})
            WITH CHECK ({_ORIGINAL_EXPR})
            """
        )
