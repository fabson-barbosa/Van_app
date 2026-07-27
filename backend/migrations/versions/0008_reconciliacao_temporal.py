"""bloco B4 — reconciliação de relógio + idempotência em eventos_aluno

Suporte de schema para o app do Motorista (CLAUDE.md §4/§8, fila offline).
Duas lacunas fechadas nesta migration:

1. **Reconciliação de relógio** (lacuna registrada em `ARQUITETURA.md` §8,
   atribuída ao B4). Até aqui, `eventos_aluno.timestamp` era o relógio do
   servidor no momento em que a API processava o evento — e é dele que saem
   `chegou_em`/`checkin_em` (motor de tempos do B3). Um evento enfileirado
   offline e sincronizado minutos/horas depois teria seu instante real
   substituído pelo instante da sincronização, colapsando trajetos inteiros
   para perto de zero. A coluna vira `ocorrido_em` (instante reconciliado:
   device_timestamp do aparelho + offset contra o relógio do servidor,
   calculado em `app/services/reconciliacao.py`) e ganha uma irmã,
   `registrado_em` (quando o servidor de fato recebeu o evento — auditoria,
   é contra ELA que a janela de 60s do desfazer-checkin é medida, nunca
   contra o relógio do aparelho — decisão de produto: medir contra o
   aparelho abriria undo infinito com relógio manipulado).

2. **Idempotência via `event_id`.** A fila offline do app pode reenviar um
   POST cuja resposta anterior se perdeu (timeout, app matado no meio). Sem
   uma chave de idempotência, o reenvio bateria na máquina de estados já fora
   do estado esperado e devolveria 409 — o motorista veria "ação não
   aplicada" para algo que já tinha sido aplicado. `event_id` é gerado no
   aparelho no momento do toque e reenviado sem trocar em cada tentativa; o
   índice único é a garantia de banco contra corrida (dois POSTs concorrentes
   com o mesmo `event_id` — o segundo INSERT perde a corrida do unique, a API
   trata isso recarregando a linha vencedora).

3. **`trip_students.checkin_registrado_em`.** A janela de 60s do
   desfazer-checkin precisa comparar DOIS relógios de servidor, não um de
   servidor contra um reconciliado — senão o lado "quando foi o checkin"
   ainda seria influenciável pelo `device_timestamp`/`device_enviado_em` que
   o próprio cliente envia (reconciliação existe para cancelar deriva
   honesta, não é prova contra um cliente adversarial). `checkin_em`
   continua sendo o instante RECONCILIADO (alimenta o motor de tempos);
   `checkin_registrado_em` é quando o servidor recebeu aquele Checkin —
   ambos os lados da comparação de janela agora são puramente
   servidor-servidor.

Achado durante a implementação: o trigger de imutabilidade de
`0004_trip_domain` (`trg_eventos_aluno_immutable`) bloqueia UPDATE na tabela
inteira, inclusive para o owner da migration — e o backfill abaixo (preencher
`registrado_em`/`event_id` nas linhas já existentes) É um UPDATE. A migration
precisa desligar o trigger antes do backfill e religá-lo depois, na mesma
transação — DDL e o `ALTER`/`UPDATE` seguem juntos, então não há janela em
que a tabela fica desprotegida entre um `alembic upgrade` e outro.

Revision ID: 0008_reconciliacao_temporal
Revises: 0007_notificacoes_e_estimativas
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008_reconciliacao_temporal"
down_revision: Union[str, None] = "0007_notificacoes_e_estimativas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TRIGGER_SQL = """
    CREATE TRIGGER trg_eventos_aluno_immutable
    BEFORE UPDATE OR DELETE ON eventos_aluno
    FOR EACH ROW EXECUTE FUNCTION forbid_update_delete_eventos_aluno();
"""


def upgrade() -> None:
    # Desliga o trigger de imutabilidade só para esta transação de migração —
    # o backfill abaixo é um UPDATE, e o trigger bloqueia UPDATE mesmo para o
    # owner (validado no gate B1->B2, ver PROGRESSO.md). A função em si
    # (`forbid_update_delete_eventos_aluno`) não muda; só o gatilho que a
    # dispara é recriado no fim.
    op.execute("DROP TRIGGER IF EXISTS trg_eventos_aluno_immutable ON eventos_aluno")

    op.alter_column("eventos_aluno", "timestamp", new_column_name="ocorrido_em")
    op.add_column("eventos_aluno", sa.Column("registrado_em", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "eventos_aluno",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    # Backfill: linhas existentes são todas de eventos processados online, então
    # servidor == ocorrência — `registrado_em` herda `ocorrido_em`. `event_id`
    # recebe um UUID novo por linha (nunca existiu antes desta migration, não
    # há reenvio possível para essas linhas).
    op.execute("UPDATE eventos_aluno SET registrado_em = ocorrido_em WHERE registrado_em IS NULL")
    op.execute("UPDATE eventos_aluno SET event_id = gen_random_uuid() WHERE event_id IS NULL")

    op.alter_column("eventos_aluno", "registrado_em", nullable=False)
    op.alter_column("eventos_aluno", "event_id", nullable=False)
    op.create_unique_constraint("uq_eventos_aluno_event_id", "eventos_aluno", ["event_id"])

    op.execute(_TRIGGER_SQL)

    # trip_students não tem trigger de imutabilidade (é a projeção mutável,
    # não o log) — coluna simples, sem backfill necessário: nenhum aluno
    # a_bordo hoje tem como saber "quando o servidor recebeu aquele checkin"
    # retroativamente, então fica NULL para viagens já em andamento (o pior
    # caso é um desfazer_checkin rejeitado por decorrido "None", tratado
    # como janela expirada — fail-safe, nunca fail-open).
    op.add_column("trip_students", sa.Column("checkin_registrado_em", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("trip_students", "checkin_registrado_em")

    op.execute("DROP TRIGGER IF EXISTS trg_eventos_aluno_immutable ON eventos_aluno")

    op.drop_constraint("uq_eventos_aluno_event_id", "eventos_aluno", type_="unique")
    op.drop_column("eventos_aluno", "event_id")
    op.drop_column("eventos_aluno", "registrado_em")
    op.alter_column("eventos_aluno", "ocorrido_em", new_column_name="timestamp")

    op.execute(_TRIGGER_SQL)
