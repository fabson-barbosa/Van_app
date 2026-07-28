"""Envio de push via Expo Push Service (Bloco B5 — fecha o `StubFCMSender` do B3).

Decisão do usuário: o app roda em Expo Go (SDK exato instalado, sem dev
client — mesma restrição do B4), então FCM direto (HTTP v1 + service
account) exigiria token nativo, que não funciona dentro do Expo Go. O Expo
Push Service (`https://exp.host/--/api/v2/push/send`) entrega no Android via
FCM por baixo, sem exigir projeto Firebase próprio — é o único caminho
viável sem sair do Expo Go. `DeviceToken.provider` guarda isso desde já
(migration `0009`) para uma futura troca para FCM direto ser um novo
`FCMSender`, não uma migration.

Implementa o `FCMSender` (Protocol de `app/services/notificacoes.py`) — quem
chama (`app/services/pos_evento.py`, `app/services/agendador.py`) não sabe
nem precisa saber que existe HTTP por trás.

Redação: o payload ESTRUTURADO continua sendo a fonte de verdade (o app
cliente re-renderiza a partir de `data`, CLAUDE.md/B3) — os textos genéricos
aqui abaixo são só o fallback exigido pelo Android para desenhar a bandeja
quando o app está em background/morto (o SO não mostra nada sem
title/body). `dismiss_chegada` é a exceção: silencioso de propósito, vira
`data-only`, o app decide o que fazer sem nunca aparecer na bandeja.

Nunca lança: falha de rede/timeout ao falar com o Expo não pode derrubar a
transação do evento de domínio que a originou (`pos_evento.py` roda isso
ANTES do commit) — mesmo contrato de "nunca falha" que `StubFCMSender` já
tinha. Erro vira log, não exceção.
"""
from __future__ import annotations

import datetime
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_token import DeviceToken

logger = logging.getLogger("vaivem.notificacoes.expo_push")

_EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_TIMEOUT_SEGUNDOS = 5.0

# Fallback de bandeja (Android/iOS exigem title/body pra desenhar algo quando
# o app não está em foreground) — a redação "de verdade" é o app cliente
# re-hidratando a partir de `data`. `None` = mensagem silenciosa (data-only).
_TEXTOS_POR_TIPO: dict[str, tuple[str, str] | None] = {
    "chegada": ("Chegamos!", "A van está esperando na parada."),
    "iminencia": ("É a próxima parada", "A van está a caminho — preparem-se."),
    "preparo": ("Prepare-se", "A van está chegando em breve."),
    "dismiss_chegada": None,
}


def _montar_mensagem(token: str, tipo: str, payload: dict) -> dict:
    texto = _TEXTOS_POR_TIPO.get(tipo)
    mensagem: dict = {"to": token, "data": {"tipo": tipo, **payload}, "priority": "high"}
    if texto is not None:
        titulo, corpo = texto
        if tipo == "preparo" and "faixa_min_baixo" in payload and "faixa_min_alto" in payload:
            corpo = f"Chegada estimada em {payload['faixa_min_baixo']}–{payload['faixa_min_alto']} min."
        mensagem["title"] = titulo
        mensagem["body"] = corpo
        mensagem["sound"] = "default"
    return mensagem


class ExpoPushSender:
    """`FCMSender` real — consulta `DeviceToken` do destinatário e entrega
    via Expo Push Service. Um usuário sem token ativo simplesmente não
    recebe nada (sem erro) — é o caso normal de quem nunca abriu o app ou
    negou permissão de notificação."""

    def __init__(self, db: Session, *, cliente: httpx.Client | None = None) -> None:
        self._db = db
        self._cliente = cliente

    def _tokens_ativos(self, destinatario_user_id) -> list[DeviceToken]:
        return list(
            self._db.scalars(
                select(DeviceToken).where(
                    DeviceToken.user_id == destinatario_user_id, DeviceToken.ativo.is_(True)
                )
            )
        )

    def _desativar_token(self, device_token: DeviceToken, motivo: str) -> None:
        device_token.ativo = False
        device_token.desativado_em = datetime.datetime.now(datetime.timezone.utc)
        logger.info("device_token_desativado token_id=%s motivo=%s", device_token.id, motivo)

    def enviar(self, *, destinatario_user_id, tipo: str, payload: dict) -> None:
        dispositivos = self._tokens_ativos(destinatario_user_id)
        if not dispositivos:
            return

        mensagens = [_montar_mensagem(d.token, tipo, payload) for d in dispositivos]
        por_token = {d.token: d for d in dispositivos}

        try:
            cliente = self._cliente or httpx.Client(timeout=_TIMEOUT_SEGUNDOS)
            resposta = cliente.post(
                _EXPO_PUSH_URL,
                json=mensagens,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
            )
            if self._cliente is None:
                cliente.close()
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("expo_push_falhou destinatario=%s tipo=%s erro=%s", destinatario_user_id, tipo, exc)
            return

        corpo = resposta.json()
        resultados = corpo.get("data", [])
        for mensagem, resultado in zip(mensagens, resultados):
            if resultado.get("status") != "error":
                continue
            detalhes = resultado.get("details") or {}
            erro = detalhes.get("error")
            logger.warning(
                "expo_push_erro destinatario=%s tipo=%s erro=%s mensagem=%s",
                destinatario_user_id, tipo, erro, resultado.get("message"),
            )
            if erro == "DeviceNotRegistered":
                device_token = por_token.get(mensagem["to"])
                if device_token is not None:
                    self._desativar_token(device_token, motivo="DeviceNotRegistered")


def build_sender(db: Session) -> ExpoPushSender:
    """Ponto único de construção — troca de sender (ex.: outro provider) é
    aqui, não espalhada pelos chamadores (`api/viagens.py`,
    `scripts/processar_notificacoes.py`)."""
    return ExpoPushSender(db)
