"""Testes de integração — Bloco B5: isolamento LGPD do `/api/responsavel`.

O ponto crítico deste bloco não é o motor de tempos (já coberto pelo B3) —
é garantir que um responsável NUNCA enxerga o filho de outro responsável,
mesmo sabendo o `aluno_id` (IDOR). Chama as funções do router diretamente
(sem subir o FastAPI/HTTP — mesmo padrão dos outros testes de integração),
passando `db`/`user` explicitamente no lugar dos `Depends(...)`.
"""
import datetime

import pytest
from fastapi import HTTPException

from app.api.responsavel import historico_filho, listar_filhos, status_filho
from app.models.evento_aluno import EventoAlunoTipo
from app.models.trip_student import TripStudentEstado
from app.models.user import UserRole
from app.schemas.auth import CurrentUser
from app.services import trip_state_machine as tsm
from tests.integration.conftest import set_tenant
from tests.integration.test_notificacoes_agendamento import _criar_cenario

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _dt(segundos: int) -> datetime.datetime:
    return T0 + datetime.timedelta(seconds=segundos)


def _current_user_do_responsavel(responsavel, tenant_id) -> CurrentUser:
    return CurrentUser(
        id=responsavel.user_id, tenant_id=tenant_id, email=f"{responsavel.user_id}@teste.com",
        role=UserRole.RESPONSAVEL,
    )


def _cenario_de_hoje(db_session, n_paradas: int = 2):
    """`_criar_cenario` usa `T0.date()` como data da viagem — sobrescreve
    pra data real de execução do teste, já que `status_filho` não aceita
    override de data (é sempre "hoje" por design)."""
    cenario = _criar_cenario(db_session, n_paradas=n_paradas)
    cenario["viagem"].data = datetime.date.today()
    db_session.commit()
    return cenario


def test_listar_filhos_nao_inclui_aluno_de_outro_responsavel(db_session):
    cenario = _cenario_de_hoje(db_session, n_paradas=2)
    set_tenant(db_session, cenario["tenant_id"])
    ts_list = cenario["trip_students"]
    responsavel_0 = cenario["responsaveis_por_aluno"][ts_list[0].aluno_id]
    user_0 = _current_user_do_responsavel(responsavel_0, cenario["tenant_id"])

    filhos = listar_filhos(db=db_session, user=user_0)

    aluno_ids = {f.aluno_id for f in filhos}
    assert aluno_ids == {ts_list[0].aluno_id}
    assert ts_list[1].aluno_id not in aluno_ids


def test_status_filho_de_outro_responsavel_e_404_nao_403(db_session):
    """404, não 403 (mesmo padrão do motorista em `api/viagens.py`) — não
    confirma pra quem pergunta que aquele `aluno_id` sequer existe."""
    cenario = _cenario_de_hoje(db_session, n_paradas=2)
    set_tenant(db_session, cenario["tenant_id"])
    ts_list = cenario["trip_students"]
    responsavel_0 = cenario["responsaveis_por_aluno"][ts_list[0].aluno_id]
    user_0 = _current_user_do_responsavel(responsavel_0, cenario["tenant_id"])
    aluno_alheio_id = ts_list[1].aluno_id

    with pytest.raises(HTTPException) as exc:
        status_filho(aluno_id=aluno_alheio_id, db=db_session, user=user_0)
    assert exc.value.status_code == 404


def test_status_filho_proprio_reflete_progresso(db_session):
    cenario = _cenario_de_hoje(db_session, n_paradas=3)
    set_tenant(db_session, cenario["tenant_id"])
    ts_list = cenario["trip_students"]
    alvo = ts_list[2]
    responsavel = cenario["responsaveis_por_aluno"][alvo.aluno_id]
    user = _current_user_do_responsavel(responsavel, cenario["tenant_id"])

    resultado = status_filho(aluno_id=alvo.aluno_id, db=db_session, user=user)

    assert resultado.tem_viagem_hoje is True
    assert resultado.viagem_status == "em_andamento"
    assert resultado.estado == TripStudentEstado.AGUARDANDO
    assert resultado.paradas_totais == 3


def test_historico_filho_de_outro_responsavel_e_404(db_session):
    cenario = _cenario_de_hoje(db_session, n_paradas=2)
    set_tenant(db_session, cenario["tenant_id"])
    ts_list = cenario["trip_students"]
    responsavel_0 = cenario["responsaveis_por_aluno"][ts_list[0].aluno_id]
    user_0 = _current_user_do_responsavel(responsavel_0, cenario["tenant_id"])

    with pytest.raises(HTTPException) as exc:
        historico_filho(aluno_id=ts_list[1].aluno_id, data=None, db=db_session, user=user_0)
    assert exc.value.status_code == 404


def test_historico_filho_mostra_eventos_reais_mas_nao_desfazer(db_session):
    cenario = _cenario_de_hoje(db_session, n_paradas=1)
    set_tenant(db_session, cenario["tenant_id"])
    viagem = cenario["viagem"]
    ts_list = cenario["trip_students"]
    alvo = ts_list[0]
    responsavel = cenario["responsaveis_por_aluno"][alvo.aluno_id]
    user = _current_user_do_responsavel(responsavel, cenario["tenant_id"])

    evt_cheguei = tsm.registrar_cheguei(viagem, alvo, ts_list, ocorrido_em=_dt(100), registrado_em=_dt(100))
    db_session.add(evt_cheguei)
    db_session.commit()
    evt_desfazer = tsm.desfazer_chegada(viagem, alvo, ocorrido_em=_dt(110), registrado_em=_dt(110))
    db_session.add(evt_desfazer)
    db_session.commit()
    evt_cheguei2 = tsm.registrar_cheguei(viagem, alvo, ts_list, ocorrido_em=_dt(120), registrado_em=_dt(120))
    db_session.add(evt_cheguei2)
    db_session.commit()

    historico = historico_filho(aluno_id=alvo.aluno_id, data=viagem.data, db=db_session, user=user)

    tipos = [e.tipo for e in historico]
    assert tipos == ["cheguei", "cheguei"]  # os 2 CHEGUEI reais aparecem, o DESFAZER_CHEGADA não
    assert EventoAlunoTipo.DESFAZER_CHEGADA.value not in tipos
