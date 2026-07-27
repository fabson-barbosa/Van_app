"""Testes unitários da máquina de estados (Bloco B2, CLAUDE.md §4/§7/§8).

Rodam sem banco: `TripStudent`/`Viagem`/`EventoAluno` são instanciados como
objetos Python puros (nenhuma sessão SQLAlchemy é aberta).

Bloco B4: os relógios são injetados via `ocorrido_em=`/`registrado_em=` (em
vez do antigo `now=` único) — nos testes que não têm motivo para divergir os
dois, `_evt(seg)` devolve o mesmo instante para ambos.
"""
import datetime
import uuid

import pytest

from app.models.evento_aluno import EventoAlunoTipo
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.viagem import Viagem, ViagemStatus
from app.services import trip_state_machine as tsm
from app.services.exceptions import (
    JanelaDesfazerExpiradaError,
    ParadaAnteriorPendenteError,
    ReordenacaoInvalidaError,
    TransicaoInvalidaError,
    TripStudentDesconhecidoError,
    VarreduraFinalPendenteError,
    ViagemStatusInvalidoError,
)

TENANT_ID = uuid.uuid4()
T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _viagem(status: ViagemStatus = ViagemStatus.EM_ANDAMENTO) -> Viagem:
    return Viagem(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        rota_id=uuid.uuid4(),
        veiculo_id=uuid.uuid4(),
        motorista_id=uuid.uuid4(),
        data=datetime.date(2026, 7, 27),
        status=status,
    )


def _trip_student(
    viagem: Viagem,
    ordem: int,
    estado: TripStudentEstado = TripStudentEstado.AGUARDANDO,
    **timestamps,
) -> TripStudent:
    return TripStudent(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        viagem_id=viagem.id,
        aluno_id=uuid.uuid4(),
        parada_id=uuid.uuid4(),
        ordem=ordem,
        estado=estado,
        **timestamps,
    )


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _clocks(segundos: int) -> dict:
    """Ocorrido_em == registrado_em — caso comum (evento online, sem deriva
    de relógio nem fila offline) usado pela maioria dos testes, que não é
    sobre reconciliação em si."""
    return {"ocorrido_em": _dt(segundos), "registrado_em": _dt(segundos)}


# ---------------------------------------------------------------------------
# Caminho feliz completo
# ---------------------------------------------------------------------------


def test_caminho_feliz_ate_entregue():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1)

    evento = tsm.registrar_cheguei(viagem, aluno, [aluno], **_clocks(0))
    assert aluno.estado == TripStudentEstado.CHEGOU
    assert aluno.chegou_em == _dt(0)
    assert evento.tipo == EventoAlunoTipo.CHEGUEI
    assert evento.estado_anterior == TripStudentEstado.AGUARDANDO

    evento = tsm.registrar_checkin(viagem, aluno, **_clocks(30))
    assert aluno.estado == TripStudentEstado.A_BORDO
    assert aluno.checkin_em == _dt(30)
    assert aluno.checkin_registrado_em == _dt(30)
    assert evento.estado_anterior == TripStudentEstado.CHEGOU

    evento = tsm.registrar_checkout(viagem, aluno, **_clocks(600))
    assert aluno.estado == TripStudentEstado.ENTREGUE
    assert aluno.checkout_em == _dt(600)
    assert evento.tipo == EventoAlunoTipo.CHECKOUT


def test_event_id_e_repassado_ao_evento_quando_informado():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1)
    event_id = uuid.uuid4()

    evento = tsm.registrar_cheguei(viagem, aluno, [aluno], **_clocks(0), event_id=event_id)

    assert evento.event_id == event_id


# ---------------------------------------------------------------------------
# Ausente — direto de aguardando (pulado) vs. vindo de chegou
# ---------------------------------------------------------------------------


def test_ausente_direto_de_aguardando_nao_seta_chegou_em():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1)

    evento = tsm.registrar_ausente(viagem, aluno, **_clocks(0))

    assert aluno.estado == TripStudentEstado.AUSENTE
    assert aluno.chegou_em is None
    assert aluno.ausente_em == _dt(0)
    assert evento.estado_anterior == TripStudentEstado.AGUARDANDO


def test_ausente_apos_chegou_preserva_chegou_em():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1)
    tsm.registrar_cheguei(viagem, aluno, [aluno], **_clocks(0))

    evento = tsm.registrar_ausente(viagem, aluno, **_clocks(120))

    assert aluno.estado == TripStudentEstado.AUSENTE
    assert aluno.chegou_em == _dt(0)
    assert evento.estado_anterior == TripStudentEstado.CHEGOU


def test_ausente_invalido_a_partir_de_entregue():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1, estado=TripStudentEstado.ENTREGUE)

    with pytest.raises(TransicaoInvalidaError):
        tsm.registrar_ausente(viagem, aluno, **_clocks(0))


# ---------------------------------------------------------------------------
# Transições inválidas básicas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "acao, estado_inicial",
    [
        ("registrar_checkin", TripStudentEstado.AGUARDANDO),
        ("registrar_checkout", TripStudentEstado.AGUARDANDO),
        ("registrar_checkout", TripStudentEstado.CHEGOU),
        ("registrar_cheguei", TripStudentEstado.CHEGOU),
        ("registrar_cheguei", TripStudentEstado.A_BORDO),
        ("desfazer_chegada", TripStudentEstado.AGUARDANDO),
        ("desfazer_chegada", TripStudentEstado.A_BORDO),
        ("desfazer_checkin", TripStudentEstado.CHEGOU),
    ],
)
def test_transicoes_invalidas_levantam_erro_explicito(acao, estado_inicial):
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1, estado=estado_inicial)

    fn = getattr(tsm, acao)
    with pytest.raises(TransicaoInvalidaError):
        if acao == "registrar_cheguei":
            fn(viagem, aluno, [aluno], **_clocks(0))
        else:
            fn(viagem, aluno, **_clocks(0))


# ---------------------------------------------------------------------------
# §7.2 — resolução forçada de parada anterior pendente
# ---------------------------------------------------------------------------


def test_cheguei_bloqueado_por_parada_anterior_pendente():
    viagem = _viagem()
    anterior = _trip_student(viagem, ordem=1, estado=TripStudentEstado.CHEGOU, chegou_em=_dt(0))
    alvo = _trip_student(viagem, ordem=2)

    with pytest.raises(ParadaAnteriorPendenteError) as exc_info:
        tsm.registrar_cheguei(viagem, alvo, [anterior, alvo], **_clocks(60))

    assert anterior in exc_info.value.pendentes
    assert alvo.estado == TripStudentEstado.AGUARDANDO  # não mutou


def test_cheguei_nao_bloqueado_por_mesma_ordem_ou_ordem_maior():
    viagem = _viagem()
    mesma_parada = _trip_student(viagem, ordem=2, estado=TripStudentEstado.CHEGOU, chegou_em=_dt(0))
    posterior_pendente = _trip_student(viagem, ordem=3, estado=TripStudentEstado.CHEGOU, chegou_em=_dt(0))
    alvo = _trip_student(viagem, ordem=2)

    tsm.registrar_cheguei(viagem, alvo, [mesma_parada, posterior_pendente, alvo], **_clocks(60))

    assert alvo.estado == TripStudentEstado.CHEGOU


# ---------------------------------------------------------------------------
# Desfazer chegada / desfazer checkin
# ---------------------------------------------------------------------------


def test_desfazer_chegada_reabre_aguardando_sem_notificacao_flag():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1, estado=TripStudentEstado.CHEGOU, chegou_em=_dt(0))

    evento = tsm.desfazer_chegada(viagem, aluno, **_clocks(10))

    assert aluno.estado == TripStudentEstado.AGUARDANDO
    assert aluno.chegou_em is None
    assert evento.tipo == EventoAlunoTipo.DESFAZER_CHEGADA


def test_desfazer_checkin_dentro_da_janela():
    viagem = _viagem()
    aluno = _trip_student(
        viagem, ordem=1, estado=TripStudentEstado.A_BORDO,
        chegou_em=_dt(0), checkin_em=_dt(30), checkin_registrado_em=_dt(30),
    )

    evento = tsm.desfazer_checkin(viagem, aluno, **_clocks(30 + 59))

    assert aluno.estado == TripStudentEstado.CHEGOU
    assert aluno.checkin_em is None
    assert aluno.checkin_registrado_em is None
    assert evento.tipo == EventoAlunoTipo.DESFAZER_CHECKIN


def test_desfazer_checkin_fora_da_janela_rejeita():
    viagem = _viagem()
    aluno = _trip_student(
        viagem, ordem=1, estado=TripStudentEstado.A_BORDO,
        chegou_em=_dt(0), checkin_em=_dt(30), checkin_registrado_em=_dt(30),
    )

    with pytest.raises(JanelaDesfazerExpiradaError):
        tsm.desfazer_checkin(viagem, aluno, **_clocks(30 + 61))

    assert aluno.estado == TripStudentEstado.A_BORDO  # não mutou


def test_desfazer_checkin_janela_medida_contra_registrado_em_nao_contra_checkin_em():
    """Bloco B4 — a janela de 60s é servidor-servidor. `checkin_em` (RECONCILIADO,
    influenciável pelo aparelho) pode divergir bastante de `checkin_registrado_em`
    (quando o servidor de fato recebeu aquele Checkin) sem afetar o resultado:
    o que importa é só a distância entre os dois `registrado_em`."""
    viagem = _viagem()
    # checkin_em "reconciliado" aponta para 10 minutos atrás (ex.: evento
    # sincronizado da fila offline, ocorrido_em bem anterior ao recebimento),
    # mas o servidor só recebeu esse Checkin há 10 segundos.
    aluno = _trip_student(
        viagem, ordem=1, estado=TripStudentEstado.A_BORDO,
        chegou_em=_dt(-700), checkin_em=_dt(-600), checkin_registrado_em=_dt(0),
    )

    # Undo pedido 10s depois do RECEBIMENTO (não do checkin_em reconciliado) —
    # dentro da janela.
    evento = tsm.desfazer_checkin(viagem, aluno, ocorrido_em=_dt(10), registrado_em=_dt(10))
    assert evento.tipo == EventoAlunoTipo.DESFAZER_CHECKIN
    assert aluno.estado == TripStudentEstado.CHEGOU


def test_desfazer_checkin_sem_checkin_registrado_em_e_fail_safe():
    """Backfill de viagens já em andamento no momento da migration 0008: sem
    `checkin_registrado_em`, o undo é tratado como janela expirada — nunca
    fail-open."""
    viagem = _viagem()
    aluno = _trip_student(
        viagem, ordem=1, estado=TripStudentEstado.A_BORDO,
        chegou_em=_dt(0), checkin_em=_dt(30), checkin_registrado_em=None,
    )

    with pytest.raises(JanelaDesfazerExpiradaError):
        tsm.desfazer_checkin(viagem, aluno, **_clocks(31))


# ---------------------------------------------------------------------------
# Guarda de status da viagem
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [ViagemStatus.PLANEJADA, ViagemStatus.FINALIZADA])
def test_evento_rejeitado_fora_de_em_andamento(status):
    viagem = _viagem(status=status)
    aluno = _trip_student(viagem, ordem=1)

    with pytest.raises(ViagemStatusInvalidoError):
        tsm.registrar_cheguei(viagem, aluno, [aluno], **_clocks(0))


# ---------------------------------------------------------------------------
# Ciclo de vida da viagem: iniciar / finalizar
# ---------------------------------------------------------------------------


def test_iniciar_viagem_cria_trip_students_em_aguardando():
    viagem = _viagem(status=ViagemStatus.PLANEJADA)
    aluno_id, parada_id = uuid.uuid4(), uuid.uuid4()

    novos = tsm.iniciar_viagem(viagem, [(aluno_id, parada_id, 1)], ocorrido_em=_dt(0))

    assert viagem.status == ViagemStatus.EM_ANDAMENTO
    assert viagem.iniciada_em == _dt(0)
    assert len(novos) == 1
    assert novos[0].aluno_id == aluno_id
    assert novos[0].parada_id == parada_id
    assert novos[0].ordem == 1
    assert novos[0].estado == TripStudentEstado.AGUARDANDO


def test_iniciar_viagem_ja_iniciada_falha():
    viagem = _viagem(status=ViagemStatus.EM_ANDAMENTO)

    with pytest.raises(ViagemStatusInvalidoError):
        tsm.iniciar_viagem(viagem, [], ocorrido_em=_dt(0))


def test_finalizar_viagem_bloqueia_com_aluno_nao_terminal():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1, estado=TripStudentEstado.A_BORDO)

    with pytest.raises(VarreduraFinalPendenteError) as exc_info:
        tsm.finalizar_viagem(viagem, [aluno], ocorrido_em=_dt(0))

    assert exc_info.value.algum_a_bordo is True
    assert viagem.status == ViagemStatus.EM_ANDAMENTO  # não mutou


def test_finalizar_viagem_com_pendente_aguardando_nao_sinaliza_a_bordo():
    viagem = _viagem()
    aluno = _trip_student(viagem, ordem=1, estado=TripStudentEstado.AGUARDANDO)

    with pytest.raises(VarreduraFinalPendenteError) as exc_info:
        tsm.finalizar_viagem(viagem, [aluno], ocorrido_em=_dt(0))

    assert exc_info.value.algum_a_bordo is False


def test_finalizar_viagem_com_todos_terminais_sucede():
    viagem = _viagem()
    entregue = _trip_student(viagem, ordem=1, estado=TripStudentEstado.ENTREGUE)
    ausente = _trip_student(viagem, ordem=2, estado=TripStudentEstado.AUSENTE)

    tsm.finalizar_viagem(viagem, [entregue, ausente], ocorrido_em=_dt(500))

    assert viagem.status == ViagemStatus.FINALIZADA
    assert viagem.finalizada_em == _dt(500)
    assert viagem.varredura_confirmada is True


# ---------------------------------------------------------------------------
# Reordenação (§8)
# ---------------------------------------------------------------------------


def test_reordenar_alunos_aguardando():
    viagem = _viagem()
    a = _trip_student(viagem, ordem=1)
    b = _trip_student(viagem, ordem=2)

    tsm.reordenar(viagem, [a, b], {a.id: 2, b.id: 1})

    assert a.ordem == 2
    assert b.ordem == 1


def test_reordenar_rejeita_aluno_que_ja_chegou():
    viagem = _viagem()
    a = _trip_student(viagem, ordem=1, estado=TripStudentEstado.CHEGOU, chegou_em=_dt(0))
    b = _trip_student(viagem, ordem=2)

    with pytest.raises(ReordenacaoInvalidaError):
        tsm.reordenar(viagem, [a, b], {a.id: 2, b.id: 1})


def test_reordenar_rejeita_trip_student_desconhecido():
    viagem = _viagem()
    a = _trip_student(viagem, ordem=1)
    id_desconhecido = uuid.uuid4()

    with pytest.raises(TripStudentDesconhecidoError):
        tsm.reordenar(viagem, [a], {a.id: 1, id_desconhecido: 2})
