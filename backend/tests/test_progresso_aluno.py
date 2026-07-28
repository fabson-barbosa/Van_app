"""Testes unitários de `pos_evento.calcular_progresso_aluno` (Bloco B5).

Sem banco: só os ramos que NÃO tocam `leg_durations`/`paradas` (estado !=
AGUARDANDO) são exercitados aqui — o caso com faixa de minutos (estado
AGUARDANDO, que consulta o banco via `_previsao_todos_os_trechos`) é coberto
em `tests/integration/test_progresso_aluno_integracao.py`.
"""
import datetime
import uuid

from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.viagem import Viagem, ViagemStatus
from app.services.pos_evento import calcular_progresso_aluno

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


def _viagem(**kwargs) -> Viagem:
    base = dict(
        id=VIAGEM_ID, tenant_id=TENANT_ID, rota_id=uuid.uuid4(), veiculo_id=uuid.uuid4(), motorista_id=uuid.uuid4(),
        data=T0.date(), status=ViagemStatus.EM_ANDAMENTO, iniciada_em=T0, atraso_manual_segundos=0,
    )
    base.update(kwargs)
    return Viagem(**base)


def test_paradas_concluidas_e_restantes_contam_por_ordem_distinta():
    # ordem 1 já tocada (chegou_em conta como âncora — `_anchor_atual`
    # considera qualquer um dos 4 timestamps de evento), alvo é a ordem 3 —
    # 1 parada concluída, 2 restantes (ordens 2 e 3) até o alvo.
    ts1 = _ts(1, TripStudentEstado.CHEGOU, chegou_em=_dt(100))
    ts2 = _ts(2)
    ts3 = _ts(3)
    # `iniciada_em=None` mantém o alvo (AGUARDANDO) fora do ramo que consulta
    # o banco — este teste cobre só a contagem de paradas, não a faixa.
    viagem = _viagem(status=ViagemStatus.PLANEJADA, iniciada_em=None)
    progresso = calcular_progresso_aluno(db=None, viagem=viagem, trip_students_ordenados=[ts1, ts2, ts3], alvo=ts3, agora=_dt(200))

    assert progresso.paradas_totais == 3
    assert progresso.paradas_concluidas == 1
    assert progresso.paradas_restantes == 2


def test_estado_chegou_expoe_chegou_em_sem_faixa():
    alvo = _ts(2, TripStudentEstado.CHEGOU, chegou_em=_dt(300))
    viagem = _viagem()
    progresso = calcular_progresso_aluno(db=None, viagem=viagem, trip_students_ordenados=[_ts(1), alvo], alvo=alvo, agora=_dt(400))

    assert progresso.estado == TripStudentEstado.CHEGOU
    assert progresso.chegou_em == _dt(300)
    assert progresso.faixa_min_baixo is None
    assert progresso.faixa_min_alto is None


def test_estado_entregue_sem_chegou_em_sem_faixa():
    alvo = _ts(1, TripStudentEstado.ENTREGUE, chegou_em=_dt(100), checkin_em=_dt(120), checkout_em=_dt(300))
    viagem = _viagem()
    progresso = calcular_progresso_aluno(db=None, viagem=viagem, trip_students_ordenados=[alvo], alvo=alvo, agora=_dt(400))

    assert progresso.chegou_em is None  # só exposto enquanto o estado É 'chegou'
    assert progresso.faixa_min_baixo is None


def test_estado_ausente_sem_faixa():
    alvo = _ts(1, TripStudentEstado.AUSENTE, ausente_em=_dt(50))
    viagem = _viagem()
    progresso = calcular_progresso_aluno(db=None, viagem=viagem, trip_students_ordenados=[alvo], alvo=alvo, agora=_dt(100))

    assert progresso.faixa_min_baixo is None
    assert progresso.faixa_min_alto is None


def test_estado_aguardando_sem_viagem_iniciada_nao_calcula_faixa_nem_toca_banco():
    # `viagem.iniciada_em is None` (planejada) — não pode calcular ETA, e não
    # pode tentar (passar db=None e cair nesse ramo derrubaria o teste).
    alvo = _ts(1)
    viagem = _viagem(status=ViagemStatus.PLANEJADA, iniciada_em=None)
    progresso = calcular_progresso_aluno(db=None, viagem=viagem, trip_students_ordenados=[alvo], alvo=alvo, agora=T0)

    assert progresso.faixa_min_baixo is None
    assert progresso.faixa_min_alto is None


def test_multiplos_alunos_na_mesma_parada_contam_uma_unica_parada():
    irmao_a = _ts(1)
    irmao_b = _ts(1)
    alvo = _ts(2)
    viagem = _viagem(status=ViagemStatus.PLANEJADA, iniciada_em=None)
    progresso = calcular_progresso_aluno(
        db=None, viagem=viagem, trip_students_ordenados=[irmao_a, irmao_b, alvo], alvo=alvo, agora=T0
    )

    assert progresso.paradas_totais == 2  # ordens distintas: 1 e 2, não 3 trip_students
