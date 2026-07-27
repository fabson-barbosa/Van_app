"""Processador do agendador de notificações (Bloco B3, CLAUDE.md §5).

Nada de sleep em memória: o "quando" mora inteiramente em
`NotificacaoAgendada.agendado_para`/`estado` (banco). Este módulo só varre o
que já venceu e ainda está `agendado`, envia (via `FCMSender`) e marca
`enviado` — chamado periodicamente por algo externo (cron, Cloud Scheduler
batendo `scripts/processar_notificacoes.py`; a orquestração de "de quanto em
quanto tempo rodar" é infra de deploy, fora do escopo aqui).
"""
from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notificacao import NotificacaoAgendada, NotificacaoEstado
from app.services import notificacoes as notif


def processar_notificacoes_pendentes(
    db: Session, agora: datetime.datetime, sender: notif.FCMSender, *, limite: int = 200
) -> int:
    """Envia toda notificação `agendado` com `agendado_para <= agora`.

    Segurança contra corrida com cancelamento concorrente (CLAUDE.md §5 —
    "CRÍTICO"): cada linha é processada em sua PRÓPRIA transação, via
    `SELECT ... FOR UPDATE SKIP LOCKED`. Se outra transação está no meio de
    cancelar essa linha (ex.: motorista faz "desfazer checkin" bem na hora
    em que o worker ia processar), o worker PULA ela nesta passada em vez de
    esperar ou enviar; na próxima passada, ou ela já virou `cancelado` (não é
    mais selecionada — nunca chega a ser enviada) ou o cancelamento não foi
    adiante (segue `agendado`, processa normalmente). A checagem de estado
    acontece dentro da MESMA transação do `UPDATE` que marca `enviado`.

    Idempotente: reprocessar (rodar de novo, cron duplicado, retry) não
    duplica envio — a 2ª passada já encontra `estado='enviado'` e a linha
    simplesmente não bate mais no filtro `estado='agendado'`. A garantia vem
    do estado persistido, nunca de deduplicação em memória.

    Retorna quantas notificações foram efetivamente enviadas nesta chamada.
    """
    total_enviadas = 0
    while total_enviadas < limite:
        pendente = db.scalars(
            select(NotificacaoAgendada)
            .where(
                NotificacaoAgendada.estado == NotificacaoEstado.AGENDADO,
                NotificacaoAgendada.agendado_para <= agora,
            )
            .order_by(NotificacaoAgendada.agendado_para)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).first()
        if pendente is None:
            break

        if pendente.estado != NotificacaoEstado.AGENDADO:  # defensivo — FOR UPDATE já garante isso
            db.commit()
            continue

        pendente.estado = NotificacaoEstado.ENVIADO
        pendente.enviado_em = agora
        sender.enviar(
            destinatario_user_id=pendente.destinatario_user_id, tipo=pendente.tipo.value, payload=pendente.payload
        )
        db.commit()
        total_enviadas += 1

    return total_enviadas
