"""Testes unitários — validação de `telefone` (E.164) em `ResponsavelCreate`/
`ResponsavelUpdate` (piloto WhatsApp via Twilio, ver PROGRESSO.md).

Sem banco: só a camada Pydantic.
"""
import uuid

import pytest
from pydantic import ValidationError

from app.models.aluno import CanalNotificacao
from app.schemas.cadastros import ResponsavelCreate, ResponsavelUpdate

_BASE = {"aluno_id": uuid.uuid4(), "user_id": uuid.uuid4()}


def test_telefone_none_e_aceito():
    r = ResponsavelCreate(**_BASE, telefone=None)
    assert r.telefone is None


@pytest.mark.parametrize("telefone", ["+5516999998888", "+14155238886", "+551633334444"])
def test_telefone_e164_valido_e_aceito(telefone):
    r = ResponsavelCreate(**_BASE, telefone=telefone)
    assert r.telefone == telefone


@pytest.mark.parametrize(
    "telefone",
    [
        "5516999998888",  # sem '+'
        "+0516999998888",  # começa com 0 depois do '+'
        "16999998888",  # sem '+' nem DDI
        "+55 16 99999-8888",  # com formatação humana
        "abc",
        "+1",
    ],
)
def test_telefone_fora_do_e164_e_rejeitado(telefone):
    with pytest.raises(ValidationError):
        ResponsavelCreate(**_BASE, telefone=telefone)


def test_telefone_invalido_e_rejeitado_no_update_tambem():
    with pytest.raises(ValidationError):
        ResponsavelUpdate(telefone="numero-invalido")


def test_canal_notificacao_default_e_push():
    r = ResponsavelCreate(**_BASE)
    assert r.canal_notificacao == CanalNotificacao.PUSH
