"""Seleção de canal por responsável (piloto WhatsApp via Twilio — não é
domínio do CLAUDE.md; decisão de produto registrada em PROGRESSO.md).

`ChannelRouterSender` implementa o mesmo `FCMSender` Protocol
(`app/services/notificacoes.py`) que `StubFCMSender`/`ExpoPushSender`/
`TwilioWhatsAppSender` — é o terceiro nível da mesma pilha, não um substituto
dela. `app/services/pos_evento.py` e `app/services/agendador.py` continuam
chamando só `sender.enviar(...)`, sem saber que existe roteamento por canal
por trás; nenhum dos dois muda.

Falha de um sub-sender (rede fora, credencial ausente, telefone inválido)
nunca propaga — cada um já garante isso por contrato próprio — então
"ambos" nunca falha por inteiro só porque um dos dois canais falhou.

`dismiss_chegada` (sinal interno para fechar a notificação persistente de
chegada, CLAUDE.md §5 — só existe no push) vai SEMPRE só para o push,
independente da preferência de canal: não existe notificação persistente no
WhatsApp para fechar (registrado como perda conhecida no PROGRESSO.md).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aluno import CanalNotificacao, Responsavel
from app.services import expo_push
from app.services import whatsapp_twilio
from app.services.notificacoes import FCMSender

_TIPO_SO_PUSH = {"dismiss_chegada"}


class ChannelRouterSender:
    def __init__(self, db: Session, *, push_sender: FCMSender, whatsapp_sender: FCMSender) -> None:
        self._db = db
        self._push_sender = push_sender
        self._whatsapp_sender = whatsapp_sender

    def _canal(self, destinatario_user_id: uuid.UUID, payload: dict) -> CanalNotificacao:
        aluno_id = payload.get("aluno_id")
        if aluno_id is None:
            return CanalNotificacao.PUSH  # sem aluno_id no payload (ex.: dismiss_chegada) — irrelevante, ver abaixo
        responsavel = self._db.scalars(
            select(Responsavel).where(
                Responsavel.user_id == destinatario_user_id, Responsavel.aluno_id == uuid.UUID(str(aluno_id))
            )
        ).first()
        return responsavel.canal_notificacao if responsavel is not None else CanalNotificacao.PUSH

    def enviar(self, *, destinatario_user_id: uuid.UUID, tipo: str, payload: dict) -> None:
        if tipo in _TIPO_SO_PUSH:
            self._push_sender.enviar(destinatario_user_id=destinatario_user_id, tipo=tipo, payload=payload)
            return

        canal = self._canal(destinatario_user_id, payload)
        if canal in (CanalNotificacao.PUSH, CanalNotificacao.AMBOS):
            self._push_sender.enviar(destinatario_user_id=destinatario_user_id, tipo=tipo, payload=payload)
        if canal in (CanalNotificacao.WHATSAPP, CanalNotificacao.AMBOS):
            self._whatsapp_sender.enviar(destinatario_user_id=destinatario_user_id, tipo=tipo, payload=payload)


def build_sender(db: Session) -> ChannelRouterSender:
    """Ponto único de construção — os dois pontos reais de envio
    (`api/viagens.py`, `scripts/processar_notificacoes.py`) importam daqui em
    vez de `expo_push.build_sender` diretamente."""
    return ChannelRouterSender(db, push_sender=expo_push.build_sender(db), whatsapp_sender=whatsapp_twilio.build_sender(db))
