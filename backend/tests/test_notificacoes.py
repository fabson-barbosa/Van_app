"""Testes unitários da cascata de notificações — parte pura (Bloco B3, CLAUDE.md §5).

Sem banco. Decisão/agendamento contra o banco fica em
`tests/integration/test_notificacoes_agendamento.py`.
"""
from app.services.notificacoes import (
    StubFCMSender,
    deve_notificar,
    faixa_minutos,
    montar_payload_preparo,
)


# ---------------------------------------------------------------------------
# faixa_minutos — nunca minuto exato (CLAUDE.md §5)
# ---------------------------------------------------------------------------


def test_faixa_minutos_arredonda_para_baixo_no_bucket_de_5():
    assert faixa_minutos(7 * 60) == (5, 10)


def test_faixa_minutos_zero_a_quatro_cai_no_bucket_zero():
    assert faixa_minutos(4 * 60 + 59) == (0, 5)


def test_faixa_minutos_exatamente_no_limite_do_bucket():
    assert faixa_minutos(10 * 60) == (10, 15)


def test_faixa_minutos_negativo_vira_bucket_zero():
    # já deveria ter chegado — não pode virar faixa negativa
    assert faixa_minutos(-120) == (0, 5)


def test_montar_payload_preparo_usa_faixa_minutos():
    assert montar_payload_preparo(7 * 60) == {"faixa_min_baixo": 5, "faixa_min_alto": 10}


# ---------------------------------------------------------------------------
# deve_notificar — Responsavel.permissoes.receber_notificacoes
# ---------------------------------------------------------------------------


def test_deve_notificar_permissivo_por_padrao_sem_a_chave():
    assert deve_notificar({}) is True


def test_deve_notificar_respeita_flag_true():
    assert deve_notificar({"receber_notificacoes": True}) is True


def test_deve_notificar_respeita_flag_false():
    assert deve_notificar({"receber_notificacoes": False}) is False


# ---------------------------------------------------------------------------
# StubFCMSender — guarda o que "enviaria"
# ---------------------------------------------------------------------------


def test_stub_sender_registra_envio():
    import uuid

    sender = StubFCMSender()
    destinatario = uuid.uuid4()
    sender.enviar(destinatario_user_id=destinatario, tipo="chegada", payload={})
    assert len(sender.enviadas) == 1
    assert sender.enviadas[0]["destinatario_user_id"] == destinatario
    assert sender.enviadas[0]["tipo"] == "chegada"
