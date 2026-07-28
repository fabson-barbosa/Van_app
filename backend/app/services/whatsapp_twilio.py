"""Envio de WhatsApp via Twilio Sandbox — piloto (não faz parte do domínio
original do CLAUDE.md; decisão de produto registrada em PROGRESSO.md).

Implementa o `FCMSender` Protocol (`app/services/notificacoes.py`) — quem
chama (via `app/services/canal_router.py`) não sabe nem precisa saber que
existe HTTP/Twilio por trás. Mesmo contrato de "nunca falha" dos outros dois
adaptadores (`StubFCMSender`, `ExpoPushSender`): falha de rede/timeout/número
inválido vira log, nunca exceção — não pode derrubar a transação do evento de
domínio nem travar a fila de agendados (`app/services/agendador.py`).

Texto é montado AQUI, não no app cliente — WhatsApp é o único canal sem app
para renderizar o payload estruturado do B3 (CLAUDE.md §5 continua valendo:
faixa de minutos, nunca minuto exato). Só nome do filho + o aviso — nada de
endereço, nada de dado de outro aluno, nada de rota.

Limitações do Sandbox (registradas em detalhe no PROGRESSO.md): número
compartilhado, destinatário precisa mandar "join <código>" e renovar a cada 3
dias, proibido em produção pelos termos da Twilio. E: a notificação
persistente com tempo correndo (`chegada` no push) não existe aqui — no
WhatsApp a chegada é sempre mensagem única.
"""
from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.aluno import Aluno, Responsavel

logger = logging.getLogger("vaivem.notificacoes.whatsapp_twilio")

_TIMEOUT_SEGUNDOS = 5.0


def _url_mensagens(account_sid: str) -> str:
    return f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


def _montar_texto(tipo: str, aluno_nome: str, payload: dict) -> str | None:
    """Três mensagens (CLAUDE.md §5/§6, adaptado ao canal sem app): sempre
    faixa de minutos, nunca minuto exato. Tipo desconhecido (ex.:
    `dismiss_chegada` — sinal interno do push, sem equivalente aqui) não gera
    texto: quem decide se um tipo deve ou não ir para o WhatsApp é o
    `canal_router`, mas este método fica defensivo mesmo assim."""
    if tipo == "preparo":
        baixo = payload.get("faixa_min_baixo")
        alto = payload.get("faixa_min_alto")
        if baixo is None or alto is None:
            return None
        return f"VaiVem: a van está chegando para {aluno_nome} em {baixo}–{alto} min. Prepare-se!"
    if tipo == "iminencia":
        return f"VaiVem: a van está a caminho — {aluno_nome} é a próxima parada."
    if tipo == "chegada":
        return f"VaiVem: a van chegou e está aguardando {aluno_nome}."
    return None


class TwilioWhatsAppSender:
    """`FCMSender` real para o canal WhatsApp. Credenciais só por variável de
    ambiente (`Settings`/.env) — nunca hardcoded, nunca commitadas. Um
    responsável sem telefone cadastrado, ou com Twilio mal configurado, só
    não recebe nada (mesmo caso normal de "sem token" no `ExpoPushSender").
    """

    def __init__(
        self,
        db: Session,
        *,
        account_sid: str | None = None,
        auth_token: str | None = None,
        whatsapp_from: str | None = None,
        cliente: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self._db = db
        self._account_sid = account_sid if account_sid is not None else settings.twilio_account_sid
        self._auth_token = auth_token if auth_token is not None else settings.twilio_auth_token
        self._whatsapp_from = whatsapp_from if whatsapp_from is not None else settings.twilio_whatsapp_from
        self._cliente = cliente

    def _responsavel_e_aluno(self, destinatario_user_id: uuid.UUID, payload: dict) -> tuple[Responsavel, Aluno] | None:
        aluno_id = payload.get("aluno_id")
        if aluno_id is None:
            return None
        responsavel = self._db.scalars(
            select(Responsavel).where(
                Responsavel.user_id == destinatario_user_id, Responsavel.aluno_id == uuid.UUID(str(aluno_id))
            )
        ).first()
        if responsavel is None or not responsavel.telefone:
            return None
        aluno = self._db.get(Aluno, responsavel.aluno_id)
        if aluno is None:
            return None
        return responsavel, aluno

    def enviar(self, *, destinatario_user_id: uuid.UUID, tipo: str, payload: dict) -> None:
        if not self._account_sid or not self._auth_token or not self._whatsapp_from:
            logger.warning("whatsapp_credenciais_ausentes destinatario=%s tipo=%s", destinatario_user_id, tipo)
            return

        encontrado = self._responsavel_e_aluno(destinatario_user_id, payload)
        if encontrado is None:
            return  # sem telefone cadastrado — caso normal, não é erro
        responsavel, aluno = encontrado

        texto = _montar_texto(tipo, aluno.nome, payload)
        if texto is None:
            return  # tipo sem redação no WhatsApp (ex.: dismiss_chegada)

        try:
            cliente = self._cliente or httpx.Client(timeout=_TIMEOUT_SEGUNDOS)
            resposta = cliente.post(
                _url_mensagens(self._account_sid),
                data={
                    "From": f"whatsapp:{self._whatsapp_from}",
                    "To": f"whatsapp:{responsavel.telefone}",
                    "Body": texto,
                },
                auth=(self._account_sid, self._auth_token),
            )
            if self._cliente is None:
                cliente.close()
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "whatsapp_envio_falhou destinatario=%s tipo=%s telefone=%s erro=%s",
                destinatario_user_id, tipo, responsavel.telefone, exc,
            )
            return

        logger.info(
            "whatsapp_envio_ok destinatario=%s tipo=%s telefone=%s", destinatario_user_id, tipo, responsavel.telefone
        )


def build_sender(db: Session) -> TwilioWhatsAppSender:
    """Ponto único de construção — mesmo padrão de `expo_push.build_sender`."""
    return TwilioWhatsAppSender(db)
