"""Testes unitários da projeção da cauda + atraso diagnóstico (Bloco B3, CLAUDE.md §5).

Sem banco — `projecao.py` é lógica pura.
"""
import datetime
import uuid

from app.services.projecao import (
    calcular_atraso_acumulado,
    previsao_acumulada_ate,
    projetar_cauda,
)

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


# ---------------------------------------------------------------------------
# previsao_acumulada_ate
# ---------------------------------------------------------------------------


def test_previsao_acumulada_soma_cumulativa():
    resultado = previsao_acumulada_ate([1, 2, 3], {1: 100.0, 2: 200.0, 3: 50.0})
    assert resultado == {1: 100.0, 2: 300.0, 3: 350.0}


def test_previsao_acumulada_ordem_sem_previsao_conta_zero():
    resultado = previsao_acumulada_ate([1, 2], {1: 100.0})
    assert resultado == {1: 100.0, 2: 100.0}


# ---------------------------------------------------------------------------
# calcular_atraso_acumulado — só diagnóstico, NÃO entra na projeção
# ---------------------------------------------------------------------------


def test_atraso_acumulado_positivo_quando_real_maior_que_previsto():
    atraso = calcular_atraso_acumulado(
        chegou_em_atual=_dt(500), iniciada_em=T0, previsto_acumulado_segundos=400
    )
    assert atraso == 100


def test_atraso_acumulado_negativo_quando_adiantado():
    # decisão explícita: não clampa em zero — adiantado é informação útil.
    atraso = calcular_atraso_acumulado(
        chegou_em_atual=_dt(300), iniciada_em=T0, previsto_acumulado_segundos=400
    )
    assert atraso == -100


def test_atraso_acumulado_zero_quando_exatamente_no_previsto():
    atraso = calcular_atraso_acumulado(
        chegou_em_atual=_dt(400), iniciada_em=T0, previsto_acumulado_segundos=400
    )
    assert atraso == 0


# ---------------------------------------------------------------------------
# projetar_cauda
# ---------------------------------------------------------------------------


def test_projetar_cauda_soma_trechos_a_partir_da_ancora():
    aluno_2 = uuid.uuid4()
    aluno_3 = uuid.uuid4()
    resultado = projetar_cauda(
        anchor_timestamp=T0, ordem_anchor=1, ordens_a_percorrer=[2, 3],
        previsao_por_ordem={2: 200.0, 3: 150.0},
        trip_students_pendentes_por_ordem={2: [aluno_2], 3: [aluno_3]},
        atraso_manual_segundos=0,
    )
    assert resultado[aluno_2] == T0 + datetime.timedelta(seconds=200)
    assert resultado[aluno_3] == T0 + datetime.timedelta(seconds=350)


def test_projetar_cauda_ignora_ordens_ate_a_ancora():
    aluno = uuid.uuid4()
    resultado = projetar_cauda(
        anchor_timestamp=T0, ordem_anchor=2, ordens_a_percorrer=[1, 2, 3],
        previsao_por_ordem={1: 999.0, 2: 999.0, 3: 100.0},
        trip_students_pendentes_por_ordem={3: [aluno]},
        atraso_manual_segundos=0,
    )
    # só o trecho 3 (>2) entra na soma — as previsões de 1 e 2 são ignoradas
    assert resultado[aluno] == T0 + datetime.timedelta(seconds=100)


def test_projetar_cauda_soma_atraso_manual_por_cima():
    aluno = uuid.uuid4()
    resultado = projetar_cauda(
        anchor_timestamp=T0, ordem_anchor=0, ordens_a_percorrer=[1],
        previsao_por_ordem={1: 100.0}, trip_students_pendentes_por_ordem={1: [aluno]},
        atraso_manual_segundos=300,
    )
    assert resultado[aluno] == T0 + datetime.timedelta(seconds=400)


def test_projetar_cauda_alunos_na_mesma_ordem_recebem_o_mesmo_eta():
    aluno_a, aluno_b = uuid.uuid4(), uuid.uuid4()
    resultado = projetar_cauda(
        anchor_timestamp=T0, ordem_anchor=0, ordens_a_percorrer=[1],
        previsao_por_ordem={1: 100.0}, trip_students_pendentes_por_ordem={1: [aluno_a, aluno_b]},
        atraso_manual_segundos=0,
    )
    assert resultado[aluno_a] == resultado[aluno_b] == T0 + datetime.timedelta(seconds=100)


def test_projetar_cauda_nao_gera_entrada_para_quem_nao_esta_pendente():
    resultado = projetar_cauda(
        anchor_timestamp=T0, ordem_anchor=0, ordens_a_percorrer=[1, 2],
        previsao_por_ordem={1: 100.0, 2: 100.0},
        trip_students_pendentes_por_ordem={2: [uuid.uuid4()]},  # ordem 1 sem pendente (ex.: já terminal)
        atraso_manual_segundos=0,
    )
    assert len(resultado) == 1
