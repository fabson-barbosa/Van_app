"""Testes unitários da reconciliação de relógio (Bloco B4).

Sem banco — `reconciliacao.py` é lógica pura.
"""
import datetime

from app.services.reconciliacao import OFFSET_MAXIMO, reconciliar

_SERVIDOR = datetime.datetime(2026, 7, 27, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(**kwargs) -> datetime.datetime:
    return _SERVIDOR + datetime.timedelta(**kwargs)


# ---------------------------------------------------------------------------
# Caso normal — offset cancela a deriva, preserva o intervalo medido
# ---------------------------------------------------------------------------


def test_relogio_do_aparelho_adiantado_e_corrigido_pelo_offset():
    # Aparelho 10min adiantado: tocou "agora" (visto pelo aparelho como 12:10),
    # enviou imediatamente (aparelho ainda mostra 12:10, servidor vê 12:00).
    resultado = reconciliar(
        device_timestamp=_dt(minutes=10),
        device_enviado_em=_dt(minutes=10),
        agora_servidor=_SERVIDOR,
    )
    assert resultado.confiavel is True
    assert resultado.ocorrido_em == _SERVIDOR  # offset = -10min aplicado de volta


def test_evento_enfileirado_offline_preserva_intervalo_medido_no_aparelho():
    # Tocou às 12:00 (hora do aparelho, sem deriva), só enviou 40min depois,
    # quando a conexão voltou. offset = 0 (aparelho não tem deriva) -> ocorrido_em
    # é exatamente o instante do toque, não o do envio.
    resultado = reconciliar(
        device_timestamp=_SERVIDOR,
        device_enviado_em=_dt(minutes=40),
        agora_servidor=_dt(minutes=40),
    )
    assert resultado.confiavel is True
    assert resultado.ocorrido_em == _SERVIDOR


def test_deriva_mais_atraso_offline_combinados():
    # Aparelho 5min atrasado, tocou e só enviou 20min depois.
    resultado = reconciliar(
        device_timestamp=_dt(minutes=-5),  # aparelho acha que são 11:55
        device_enviado_em=_dt(minutes=15),  # aparelho acha que são 12:15 ao enviar (20min depois do toque)
        agora_servidor=_dt(minutes=20),  # servidor: 12:20
        nao_antes_de=_dt(hours=-1),
    )
    # offset = agora_servidor - device_enviado_em = 12:20 - 12:15 = +5min
    # ocorrido_em = device_timestamp + offset = 11:55 + 5min = 12:00
    assert resultado.confiavel is True
    assert resultado.ocorrido_em == _SERVIDOR


# ---------------------------------------------------------------------------
# Fallback — dados ausentes
# ---------------------------------------------------------------------------


def test_sem_device_timestamp_cai_no_relogio_do_servidor():
    resultado = reconciliar(device_timestamp=None, device_enviado_em=_SERVIDOR, agora_servidor=_SERVIDOR)
    assert resultado.ocorrido_em == _SERVIDOR
    assert resultado.confiavel is False


def test_sem_device_enviado_em_cai_no_relogio_do_servidor():
    resultado = reconciliar(device_timestamp=_SERVIDOR, device_enviado_em=None, agora_servidor=_SERVIDOR)
    assert resultado.ocorrido_em == _SERVIDOR
    assert resultado.confiavel is False


# ---------------------------------------------------------------------------
# Clamp de offset (±24h)
# ---------------------------------------------------------------------------


def test_offset_dentro_do_limite_e_aceito():
    resultado = reconciliar(
        device_timestamp=_SERVIDOR - OFFSET_MAXIMO + datetime.timedelta(minutes=1),
        device_enviado_em=_SERVIDOR - OFFSET_MAXIMO + datetime.timedelta(minutes=1),
        agora_servidor=_SERVIDOR,
    )
    assert resultado.confiavel is True


def test_offset_estourando_24h_cai_no_relogio_do_servidor():
    resultado = reconciliar(
        device_timestamp=_SERVIDOR - datetime.timedelta(hours=25),
        device_enviado_em=_SERVIDOR - datetime.timedelta(hours=25),
        agora_servidor=_SERVIDOR,
    )
    assert resultado.ocorrido_em == _SERVIDOR
    assert resultado.confiavel is False


def test_offset_negativo_estourando_24h_tambem_e_rejeitado():
    resultado = reconciliar(
        device_timestamp=_SERVIDOR + datetime.timedelta(hours=25),
        device_enviado_em=_SERVIDOR - datetime.timedelta(hours=25),
        agora_servidor=_SERVIDOR,
    )
    assert resultado.confiavel is False


# ---------------------------------------------------------------------------
# Clamps de sanidade — nunca no futuro, nunca antes do início da viagem
# ---------------------------------------------------------------------------


def test_resultado_no_futuro_do_servidor_e_rejeitado():
    # device_enviado_em no passado (relógio do aparelho atrasado na hora do
    # envio) faz o offset ser positivo o bastante para jogar ocorrido_em
    # depois de agora_servidor.
    resultado = reconciliar(
        device_timestamp=_SERVIDOR,
        device_enviado_em=_SERVIDOR - datetime.timedelta(minutes=30),
        agora_servidor=_SERVIDOR,
    )
    assert resultado.confiavel is False
    assert resultado.ocorrido_em == _SERVIDOR


def test_resultado_antes_do_inicio_da_viagem_e_rejeitado():
    inicio_viagem = _SERVIDOR
    resultado = reconciliar(
        device_timestamp=_SERVIDOR - datetime.timedelta(hours=1),
        device_enviado_em=_SERVIDOR,
        agora_servidor=_SERVIDOR,
        nao_antes_de=inicio_viagem,
    )
    assert resultado.confiavel is False
    assert resultado.ocorrido_em == _SERVIDOR


def test_sem_nao_antes_de_nao_aplica_esse_clamp():
    resultado = reconciliar(
        device_timestamp=_SERVIDOR - datetime.timedelta(hours=1),
        device_enviado_em=_SERVIDOR,
        agora_servidor=_SERVIDOR,
        nao_antes_de=None,
    )
    assert resultado.confiavel is True
    assert resultado.ocorrido_em == _SERVIDOR - datetime.timedelta(hours=1)
