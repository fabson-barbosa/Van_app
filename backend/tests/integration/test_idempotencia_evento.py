"""Teste de integração obrigatório (Bloco B4, aprovado pelo usuário antes da
implementação): a fila offline do app do Motorista pode reenviar um POST cuja
resposta anterior se perdeu (timeout, app matado no meio) — sem uma chave de
idempotência, o reenvio bateria na máquina de estados já fora do estado
esperado e devolveria 409 ("ação não aplicada" para algo que já foi
aplicado). `event_id` (gerado no aparelho, reenviado sem trocar) resolve
isso em dois níveis:

1. Pré-checagem (`app/api/viagens.py::_evento_ja_processado`) — o caminho
   normal: a resposta do primeiro POST se perdeu, mas ele JÁ comitou; o
   reenvio encontra o evento existente e devolve 200 com o estado atual, sem
   reprocessar a máquina de estados.
2. Corrida (`_registrar_evento`, catch de `IntegrityError`) — dois POSTs com
   o mesmo `event_id` passam pela pré-checagem antes de qualquer um comitar;
   o índice único `uq_eventos_aluno_event_id` (migration 0008) garante um
   único vencedor, e o perdedor recebe de volta o estado do vencedor em vez
   de um 500.
"""
import datetime
import uuid

import pytest
from fastapi import HTTPException
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from sqlalchemy import select

from app.api import viagens as viagens_api
from app.core.security import hash_password
from app.models.aluno import Aluno
from app.models.evento_aluno import EventoAluno, EventoAlunoTipo
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.tenant import Tenant
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.user import User, UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.schemas.auth import CurrentUser
from app.schemas.viagens import EventoAlunoRequest
from app.services import trip_state_machine as tsm
from tests.integration.conftest import set_tenant

pytestmark = pytest.mark.integration

T0 = datetime.datetime(2026, 7, 27, 7, 0, 0, tzinfo=datetime.timezone.utc)


def _criar_cenario(session):
    """Tenant + motorista/veículo/rota/parada/aluno + viagem EM_ANDAMENTO com
    1 trip_student em 'aguardando' — pronto para um Cheguei."""
    tenant = Tenant(id=uuid.uuid4(), nome=f"Tenant Idempotencia {uuid.uuid4()}", plano="pro", status_billing="ativo")
    session.add(tenant)
    session.flush()
    set_tenant(session, tenant.id)

    motorista_user = User(
        id=uuid.uuid4(), tenant_id=tenant.id, nome="Motorista", email=f"m.{uuid.uuid4()}@teste.com",
        senha_hash=hash_password("x"), role=UserRole.MOTORISTA, ativo=True,
    )
    session.add(motorista_user)
    session.flush()
    motorista = Motorista(id=uuid.uuid4(), tenant_id=tenant.id, user_id=motorista_user.id, ativo=True)
    session.add(motorista)
    veiculo = Veiculo(id=uuid.uuid4(), tenant_id=tenant.id, placa="IDP0001", km_atual=0)
    session.add(veiculo)
    rota = Rota(id=uuid.uuid4(), tenant_id=tenant.id, nome="Rota Idempotencia", turno="manha", ativa=True)
    session.add(rota)
    session.flush()
    parada = Parada(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, nome="Parada 1", ordem_base=1,
        geo=from_shape(Point(-46.6, -23.5), srid=4326),
    )
    session.add(parada)
    session.flush()
    aluno = Aluno(id=uuid.uuid4(), tenant_id=tenant.id, nome="Aluno", parada_id=parada.id, ativo=True)
    session.add(aluno)
    session.flush()

    viagem = Viagem(
        id=uuid.uuid4(), tenant_id=tenant.id, rota_id=rota.id, veiculo_id=veiculo.id, motorista_id=motorista.id,
        data=T0.date(), status=ViagemStatus.EM_ANDAMENTO, iniciada_em=T0,
    )
    session.add(viagem)
    session.flush()
    trip_student = TripStudent(
        id=uuid.uuid4(), tenant_id=tenant.id, viagem_id=viagem.id, aluno_id=aluno.id, parada_id=parada.id,
        ordem=1, estado=TripStudentEstado.AGUARDANDO,
    )
    session.add(trip_student)
    session.commit()

    return tenant.id, motorista_user.id, viagem, trip_student


# ---------------------------------------------------------------------------
# Caminho normal — reenvio depois que a resposta original se perdeu
# ---------------------------------------------------------------------------


def test_reenvio_com_mesmo_event_id_nao_duplica_e_devolve_estado_atual(db_session):
    tenant_id, motorista_user_id, viagem, trip_student = _criar_cenario(db_session)
    set_tenant(db_session, tenant_id)
    user = CurrentUser(id=motorista_user_id, tenant_id=tenant_id, email="m@teste.com", role=UserRole.MOTORISTA)
    event_id = uuid.uuid4()
    payload = EventoAlunoRequest(event_id=event_id)

    primeira = viagens_api.marcar_cheguei(viagem.id, trip_student.id, payload, db_session, user)
    assert primeira.estado == TripStudentEstado.CHEGOU

    # Reenvio da fila offline: mesmo event_id, mesmo payload — a resposta da
    # primeira chamada "se perdeu" do ponto de vista do app, mas o evento já
    # foi persistido. Não pode virar 409 (TransicaoInvalidaError, já que o
    # aluno não está mais 'aguardando').
    segunda = viagens_api.marcar_cheguei(viagem.id, trip_student.id, payload, db_session, user)
    assert segunda.estado == TripStudentEstado.CHEGOU
    assert segunda.id == primeira.id

    eventos = db_session.scalars(select(EventoAluno).where(EventoAluno.event_id == event_id)).all()
    assert len(eventos) == 1, "reenvio não deveria gravar um segundo evento"


def test_event_ids_diferentes_para_a_mesma_acao_sao_eventos_distintos(db_session):
    """Contraprova: dois `event_id` diferentes IMPLICAM duas tentativas
    genuinamente diferentes — a segunda bate na máquina de estados fora do
    estado esperado e recebe 409 de verdade (idempotência não deve mascarar
    um erro real de domínio)."""
    tenant_id, motorista_user_id, viagem, trip_student = _criar_cenario(db_session)
    set_tenant(db_session, tenant_id)
    user = CurrentUser(id=motorista_user_id, tenant_id=tenant_id, email="m@teste.com", role=UserRole.MOTORISTA)

    viagens_api.marcar_cheguei(viagem.id, trip_student.id, EventoAlunoRequest(event_id=uuid.uuid4()), db_session, user)

    with pytest.raises(HTTPException) as exc_info:
        viagens_api.marcar_cheguei(
            viagem.id, trip_student.id, EventoAlunoRequest(event_id=uuid.uuid4()), db_session, user
        )
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# CRÍTICO — corrida: dois INSERTs com o mesmo event_id
# ---------------------------------------------------------------------------


def test_insercao_concorrente_do_mesmo_event_id_e_resolvida_pelo_indice_unico(db_session):
    """Reproduz o DESFECHO da corrida (duas requisições que passaram pela
    pré-checagem de idempotência antes de qualquer uma comitar, então ambas
    tentam INSERIR um `EventoAluno` com o mesmo `event_id`) sem precisar de
    threads reais: o vencedor comita primeiro; o "perdedor" é construído
    manualmente (não via `tsm.registrar_cheguei` de novo, que rejeitaria a
    transição porque o `trip_student` já mudou de estado — é exatamente essa
    situação que a corrida real evitaria, já que as duas partiriam do mesmo
    'aguardando') e submetido direto a `_registrar_evento`, que é onde o
    catch de `IntegrityError` mora.
    """
    tenant_id, motorista_user_id, viagem, trip_student = _criar_cenario(db_session)
    set_tenant(db_session, tenant_id)
    event_id = uuid.uuid4()
    agora = datetime.datetime.now(datetime.timezone.utc)
    outros = [trip_student]

    evento_vencedor = tsm.registrar_cheguei(
        viagem, trip_student, outros, ocorrido_em=agora, registrado_em=agora, event_id=event_id,
    )
    resultado_vencedor = viagens_api._registrar_evento(db_session, viagem, trip_student, evento_vencedor, outros)
    assert resultado_vencedor.estado == TripStudentEstado.CHEGOU

    evento_perdedor = EventoAluno(
        tenant_id=trip_student.tenant_id, trip_student_id=trip_student.id, tipo=EventoAlunoTipo.CHEGUEI,
        estado_anterior=TripStudentEstado.AGUARDANDO, ocorrido_em=agora, registrado_em=agora, event_id=event_id,
    )
    resultado_perdedor = viagens_api._registrar_evento(db_session, viagem, trip_student, evento_perdedor, outros)

    assert resultado_perdedor.id == trip_student.id
    assert resultado_perdedor.estado == TripStudentEstado.CHEGOU, "deveria devolver o estado do vencedor, não 500"

    eventos = db_session.scalars(select(EventoAluno).where(EventoAluno.event_id == event_id)).all()
    assert len(eventos) == 1, "o índice único deveria ter impedido o segundo INSERT"
