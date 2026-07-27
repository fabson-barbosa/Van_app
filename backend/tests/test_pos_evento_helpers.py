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
    PREPARO_ANTECEDENCIA_SEGUNDOS,
    _agendado_para_preparo,
    _anchor_atual,
    _eta_parada_anterior,
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


# ---------------------------------------------------------------------------
# _eta_parada_anterior / _agendado_para_preparo — a cascata não pode inverter
# (CLAUDE.md §5: antecedência do preparo é POSICIONAL, não temporal)
# ---------------------------------------------------------------------------


def test_eta_parada_anterior_usa_a_ordem_imediatamente_antes_do_alvo():
    etas_ordem = {1: _dt(60), 2: _dt(150), 3: _dt(400)}
    resultado = _eta_parada_anterior([1, 2, 3], etas_ordem, anchor_timestamp=T0, ordem_alvo=3)
    assert resultado == _dt(150)  # ordem 2, não ordem 1


def test_eta_parada_anterior_sem_intermediaria_usa_a_ancora():
    etas_ordem = {5: _dt(300)}
    resultado = _eta_parada_anterior([5], etas_ordem, anchor_timestamp=T0, ordem_alvo=5)
    assert resultado == T0


def test_agendado_para_preparo_usa_o_piso_de_5min_quando_o_trecho_da_espaco():
    # trecho longo: ETA(alvo)=20min, parada anterior a 15min — 5min de
    # antecedência cabem sem esbarrar no teto.
    agendado = _agendado_para_preparo(agora=T0, eta_alvo=_dt(1200), eta_parada_anterior=_dt(900))
    assert agendado == _dt(1200 - PREPARO_ANTECEDENCIA_SEGUNDOS)  # 900 = 15min, ainda dentro do teto


def test_agendado_para_preparo_trecho_curto_ate_a_proxima_parada_nao_inverte_com_iminencia():
    # Regressão explícita pedida: trecho curto (2-3min) ATÉ A PRÓXIMA PARADA
    # (N+1) faz "é a próxima" (iminência de N+2) disparar logo — um piso fixo
    # de 5min antes do ETA de N+2, sozinho, agendaria o preparo DEPOIS disso
    # (a cascata inverte). O trecho seguinte (N+1 -> N+2) é normal (10min),
    # então sem o teto o candidato (5min antes do ETA de N+2) passaria longe
    # do ETA de N+1.
    eta_parada_anterior = _dt(150)  # trecho curto até N+1: 2,5min desde a âncora
    eta_alvo = _dt(150 + 10 * 60)  # + trecho normal até N+2 (10min) = 12,5min totais
    agendado = _agendado_para_preparo(agora=T0, eta_alvo=eta_alvo, eta_parada_anterior=eta_parada_anterior)
    assert agendado <= eta_parada_anterior
    assert agendado == eta_parada_anterior  # teto ativo — sem ele daria 450s (7,5min), depois da iminência (150s)


def test_agendado_para_preparo_nunca_no_passado():
    # se até o teto (parada anterior) já passou, cai no piso `agora` — o
    # agendador processa como "vencido" na próxima passada, não quebra.
    agendado = _agendado_para_preparo(agora=T0, eta_alvo=_dt(-500), eta_parada_anterior=_dt(-600))
    assert agendado == _dt(-600)  # teto < agora: fica no teto mesmo, "atrasado" — ver docstring
