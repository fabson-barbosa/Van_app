"""Testes unitários dos helpers de posicionamento de `pos_evento.py` (Bloco B3).

Sem banco — operam só sobre listas de `TripStudent` já carregadas (o mesmo
padrão de `trip_state_machine.py`: instancia os models como objetos Python
puros, nenhuma sessão é aberta). Cobre a parte de "aritmética de tempos"
(trajeto vs. casa pulada) que não depende de acesso a `leg_durations`.
"""
import datetime
import uuid

from app.models.trip_student import TripStudent, TripStudentEstado
from app.services.pos_evento import (
    _anchor_atual,
    _n_esimo_nao_terminal,
    _nao_terminais_apos,
    _ordem_anterior_info,
)

TENANT_ID = uuid.uuid4()
VIAGEM_ID = uuid.uuid4()
T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _ts(ordem: int, estado: TripStudentEstado = TripStudentEstado.AGUARDANDO, **timestamps) -> TripStudent:
    return TripStudent(
        id=uuid.uuid4(), tenant_id=TENANT_ID, viagem_id=VIAGEM_ID, aluno_id=uuid.uuid4(),
        parada_id=uuid.uuid4(), ordem=ordem, estado=estado, **timestamps,
    )


# ---------------------------------------------------------------------------
# _nao_terminais_apos / _n_esimo_nao_terminal — pula ausente/entregue (N+1/N+2)
# ---------------------------------------------------------------------------


def test_n_esimo_nao_terminal_pula_ausente():
    ts1 = _ts(1, TripStudentEstado.ENTREGUE)
    ts2 = _ts(2, TripStudentEstado.AUSENTE)  # pulado
    ts3 = _ts(3, TripStudentEstado.AGUARDANDO)
    ts4 = _ts(4, TripStudentEstado.AGUARDANDO)
    lista = [ts1, ts2, ts3, ts4]

    proximo = _n_esimo_nao_terminal(lista, ordem_apos=1, posicao=1)
    depois = _n_esimo_nao_terminal(lista, ordem_apos=1, posicao=2)

    assert proximo is ts3  # ts2 (ausente) não conta
    assert depois is ts4


def test_n_esimo_nao_terminal_retorna_none_se_nao_ha_suficientes():
    lista = [_ts(1), _ts(2, TripStudentEstado.ENTREGUE)]
    assert _n_esimo_nao_terminal(lista, ordem_apos=1, posicao=1) is None


def test_nao_terminais_apos_ordena_por_ordem():
    ts3 = _ts(3)
    ts2 = _ts(2)
    lista = [ts3, ts2]  # fora de ordem de propósito
    resultado = _nao_terminais_apos(lista, ordem_apos=1)
    assert resultado == [ts2, ts3]


# ---------------------------------------------------------------------------
# _ordem_anterior_info — trajeto vs. casa pulada (CLAUDE.md §4/§5)
# ---------------------------------------------------------------------------


def test_ordem_anterior_info_primeira_parada_nao_tem_anterior():
    lista = [_ts(1)]
    ordem_anterior, anchor = _ordem_anterior_info(lista, ordem_atual=1)
    assert ordem_anterior is None
    assert anchor is None


def test_ordem_anterior_info_usa_checkin_da_parada_anterior():
    anterior = _ts(1, TripStudentEstado.A_BORDO, checkin_em=_dt(100))
    lista = [anterior, _ts(2)]
    ordem_anterior, anchor = _ordem_anterior_info(lista, ordem_atual=2)
    assert ordem_anterior == 1
    assert anchor == _dt(100)


def test_ordem_anterior_info_casa_pulada_sem_checkin_retorna_anchor_none():
    anterior_ausente = _ts(1, TripStudentEstado.AUSENTE, ausente_em=_dt(50))  # sem checkin_em
    lista = [anterior_ausente, _ts(2)]
    ordem_anterior, anchor = _ordem_anterior_info(lista, ordem_atual=2)
    assert ordem_anterior == 1
    assert anchor is None  # sinal para o chamador descartar a amostra


def test_ordem_anterior_info_multiplos_na_mesma_ordem_usa_o_checkin_mais_tardio():
    irmao_a = _ts(1, TripStudentEstado.A_BORDO, checkin_em=_dt(100))
    irmao_b = _ts(1, TripStudentEstado.A_BORDO, checkin_em=_dt(150))
    lista = [irmao_a, irmao_b, _ts(2)]
    _, anchor = _ordem_anterior_info(lista, ordem_atual=2)
    assert anchor == _dt(150)


# ---------------------------------------------------------------------------
# _anchor_atual — onde a viagem está "agora"
# ---------------------------------------------------------------------------


def test_anchor_atual_viagem_recem_iniciada_usa_iniciada_em():
    lista = [_ts(1), _ts(2)]
    anchor_timestamp, ordem_anchor = _anchor_atual(lista, iniciada_em=T0)
    assert anchor_timestamp == T0
    assert ordem_anchor == -1  # sentinela: nada aconteceu ainda


def test_anchor_atual_usa_o_timestamp_mais_recente_e_a_maior_ordem_tocada():
    ts1 = _ts(1, TripStudentEstado.ENTREGUE, chegou_em=_dt(100), checkin_em=_dt(110), checkout_em=_dt(200))
    ts2 = _ts(2, TripStudentEstado.CHEGOU, chegou_em=_dt(300))
    ts3 = _ts(3)  # ainda intocado
    anchor_timestamp, ordem_anchor = _anchor_atual([ts1, ts2, ts3], iniciada_em=T0)
    assert anchor_timestamp == _dt(300)
    assert ordem_anchor == 2
