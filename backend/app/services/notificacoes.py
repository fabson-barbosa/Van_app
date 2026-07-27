"""Cascata de notificações — decisão + envio (Bloco B3, CLAUDE.md §5).

`NotificacaoSpec`/`montar_payload_preparo`/`faixa_minutos` são lógica pura
(sem banco). Quem decide QUANDO agendar/cancelar (ligado aos eventos da
máquina de estados) e persiste é `app/services/pos_evento.py`; este módulo só
sabe montar o conteúdo de uma notificação e mandar (via `FCMSender`).

Payload é dado ESTRUTURADO, não texto pronto — a redação (i18n, tom) é do
app cliente (B4/B5, fora de escopo). O que garantimos aqui é que a faixa
nunca vira minuto exato (CLAUDE.md §5: "faixa de minutos, nunca minuto
exato").
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

logger = logging.getLogger("vaivem.notificacoes")

FAIXA_MINUTOS_TAMANHO = 5

# Motivos de cancelamento (CLAUDE.md §5 — gatilhos críticos de cancelamento).
MOTIVO_DESFAZER_CHECKIN = "desfazer_checkin: base do agendamento deixou de existir"
MOTIVO_AUSENTE = "aluno marcado ausente: preparo não faz mais sentido"
MOTIVO_REORDENAR = "parada reordenada: relação N/N+2 mudou"
MOTIVO_TERMINAL = "aluno chegou a estado terminal (entregue): preparo pendente não faz mais sentido"


@dataclass(frozen=True)
class NotificacaoSpec:
    """O que criar/reagendar — `pos_evento.py` decide o resto (upsert no banco)."""

    trip_student_id: uuid.UUID
    destinatario_user_id: uuid.UUID
    tipo: str  # NotificacaoTipo.value
    agendado_para: datetime
    payload: dict = field(default_factory=dict)


def faixa_minutos(segundos_restantes: float, *, tamanho_bucket_min: int = FAIXA_MINUTOS_TAMANHO) -> tuple[int, int]:
    """Arredonda segundos para uma FAIXA de minutos, nunca o minuto exato.

    Ex.: 7min -> (5, 10). Negativo (já deveria ter chegado) vira (0, tamanho).
    """
    minutos = max(0.0, segundos_restantes / 60.0)
    baixo = int(minutos // tamanho_bucket_min) * tamanho_bucket_min
    return baixo, baixo + tamanho_bucket_min


def montar_payload_preparo(segundos_restantes: float) -> dict:
    baixo, alto = faixa_minutos(segundos_restantes)
    return {"faixa_min_baixo": baixo, "faixa_min_alto": alto}


def deve_notificar(permissoes: dict) -> bool:
    """`Responsavel.permissoes` (JSONB) — permissivo por padrão se a chave
    não existir (não quebra responsáveis cadastrados antes desta flag)."""
    return bool(permissoes.get("receber_notificacoes", True))


class FCMSender(Protocol):
    def enviar(self, *, destinatario_user_id: uuid.UUID, tipo: str, payload: dict) -> None: ...


class StubFCMSender:
    """Stub — sem integração real de push. Guarda o que "enviaria" para
    inspeção em teste/log; a interface real de FCM fica para depois."""

    def __init__(self) -> None:
        self.enviadas: list[dict] = []

    def enviar(self, *, destinatario_user_id: uuid.UUID, tipo: str, payload: dict) -> None:
        registro = {"destinatario_user_id": destinatario_user_id, "tipo": tipo, "payload": payload}
        self.enviadas.append(registro)
        logger.info("notificacao_enviada(stub) destinatario=%s tipo=%s payload=%s", destinatario_user_id, tipo, payload)
