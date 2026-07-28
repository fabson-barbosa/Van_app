"""Motor de viagem — máquina de estados do aluno, ciclo de vida da viagem
e varredura final (Bloco B2, CLAUDE.md §4/§7/§8/§9).

Endpoints finos: validam, delegam a `services/trip_state_machine.py` (lógica
pura) e serializam. Toda regra de negócio (transições, §7.1, §7.2, §8) vive
no service — aqui só orquestração de banco e tradução de erro de domínio
para HTTP.

Autorização: `admin`, `motorista` e `motorista_backup` operam viagens
(`motorista_backup` existe justamente para assumir uma viagem em andamento
se o aparelho do motorista titular falhar — CLAUDE.md §3/§11). Fora do papel
`admin`, o acesso é restrito às viagens do próprio motorista — devolvemos 404
em vez de 403 para não confirmar a existência de viagens de outro motorista.

Bloco B4 (app Motorista): três acréscimos nos 6 endpoints de evento —
1. `ViagemOut`/`TripStudentOut` enriquecidos com nome/endereço/contadores via
   join (`_viagem_out`/`_trip_student_out` abaixo), porque `/api/alunos` e
   `/api/rotas/{id}/paradas` são admin-only e o motorista não tem outro jeito
   de ver essa informação (minimização de dados, LGPD — ver PROGRESSO.md B4).
2. Reconciliação de relógio (`app/services/reconciliacao.py`) antes de cada
   chamada a `trip_state_machine` — `ocorrido_em` (reconciliado) alimenta o
   motor de tempos, `registrado_em` (relógio do servidor) é só auditoria e a
   âncora da janela de desfazer-checkin.
3. Idempotência via `event_id`: um reenvio da fila offline com o mesmo
   `event_id` não reprocessa — devolve o estado atual (200), nunca um 409
   espúrio.
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.aluno import Aluno
from app.models.evento_aluno import EventoAluno, EventoAlunoTipo
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.trip_student import TripStudent
from app.models.user import UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem, ViagemStatus
from app.schemas.auth import CurrentUser
from app.schemas.viagens import (
    EstouAtrasadoRequest,
    EventoAlunoRequest,
    ReordenarRequest,
    TripStudentOut,
    ViagemCreate,
    ViagemOut,
)
from app.services import pos_evento
from app.services import trip_state_machine as tsm
from app.services.exceptions import DominioError, ViagemStatusInvalidoError
from app.services.expo_push import build_sender
from app.services.reconciliacao import reconciliar

router = APIRouter(prefix="/api/viagens", tags=["viagens"])

_VIAGEM_NAO_ENCONTRADA = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Viagem não encontrada.")
_TRIP_STUDENT_NAO_ENCONTRADO = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="Aluno não encontrado nesta viagem."
)
_ROTA_INVALIDA = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rota não encontrada para este tenant.")
_VEICULO_INVALIDO = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST, detail="Veículo não encontrado para este tenant."
)
_MOTORISTA_INVALIDO = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST, detail="Motorista não encontrado para este tenant."
)

_PAPEIS_OPERACAO = ("admin", "motorista", "motorista_backup")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _mapear_erro_dominio(exc: DominioError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _get_viagem_ou_404(db: Session, viagem_id: uuid.UUID) -> Viagem:
    viagem = db.get(Viagem, viagem_id)
    if viagem is None:
        raise _VIAGEM_NAO_ENCONTRADA
    return viagem


def _garantir_acesso_viagem(db: Session, viagem: Viagem, user: CurrentUser) -> None:
    """Fora do papel admin, só o motorista dono da viagem pode acessá-la/operá-la."""
    if user.role == UserRole.ADMIN:
        return
    motorista = db.scalars(select(Motorista).where(Motorista.user_id == user.id)).first()
    if motorista is None or viagem.motorista_id != motorista.id:
        raise _VIAGEM_NAO_ENCONTRADA


def _get_viagem_autorizada(db: Session, viagem_id: uuid.UUID, user: CurrentUser) -> Viagem:
    viagem = _get_viagem_ou_404(db, viagem_id)
    _garantir_acesso_viagem(db, viagem, user)
    return viagem


def _get_trip_student_ou_404(db: Session, viagem: Viagem, trip_student_id: uuid.UUID) -> TripStudent:
    trip_student = db.get(TripStudent, trip_student_id)
    if trip_student is None or trip_student.viagem_id != viagem.id:
        raise _TRIP_STUDENT_NAO_ENCONTRADO
    return trip_student


def _listar_trip_students(db: Session, viagem: Viagem) -> list[TripStudent]:
    return list(
        db.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id).order_by(TripStudent.ordem))
    )


def _validar_rota(db: Session, rota_id: uuid.UUID) -> None:
    if db.get(Rota, rota_id) is None:
        raise _ROTA_INVALIDA


def _validar_veiculo(db: Session, veiculo_id: uuid.UUID) -> None:
    if db.get(Veiculo, veiculo_id) is None:
        raise _VEICULO_INVALIDO


def _validar_motorista(db: Session, motorista_id: uuid.UUID) -> None:
    if db.get(Motorista, motorista_id) is None:
        raise _MOTORISTA_INVALIDO


def _contagem_alunos_por_rota(db: Session, rota_ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not rota_ids:
        return {}
    linhas = db.execute(
        select(Parada.rota_id, func.count(Aluno.id))
        .join(Aluno, Aluno.parada_id == Parada.id)
        .where(Parada.rota_id.in_(rota_ids), Aluno.ativo.is_(True))
        .group_by(Parada.rota_id)
    ).all()
    return dict(linhas)


def _viagens_out(db: Session, viagens: list[Viagem]) -> list[ViagemOut]:
    """Enriquecido para o app do Motorista (Bloco B4) — ver docstring do módulo."""
    rota_ids = {v.rota_id for v in viagens}
    rotas = {r.id: r for r in db.scalars(select(Rota).where(Rota.id.in_(rota_ids)))} if rota_ids else {}
    contagens = _contagem_alunos_por_rota(db, rota_ids)

    resultado = []
    for v in viagens:
        rota = rotas.get(v.rota_id)
        resultado.append(
            ViagemOut(
                id=v.id, tenant_id=v.tenant_id, rota_id=v.rota_id, veiculo_id=v.veiculo_id,
                motorista_id=v.motorista_id, data=v.data, status=v.status,
                iniciada_em=v.iniciada_em, finalizada_em=v.finalizada_em,
                atraso_acumulado_segundos=v.atraso_acumulado_segundos,
                varredura_confirmada=v.varredura_confirmada,
                created_at=v.created_at, updated_at=v.updated_at,
                rota_nome=rota.nome if rota else "?", rota_turno=rota.turno if rota else "?",
                rota_escola=rota.escola if rota else None, total_alunos=contagens.get(v.rota_id, 0),
            )
        )
    return resultado


def _viagem_out(db: Session, viagem: Viagem) -> ViagemOut:
    return _viagens_out(db, [viagem])[0]


def _trip_students_out(db: Session, trip_students: list[TripStudent]) -> list[TripStudentOut]:
    """Enriquecido para o app do Motorista (Bloco B4) — ver docstring do módulo."""
    aluno_ids = {ts.aluno_id for ts in trip_students}
    parada_ids = {ts.parada_id for ts in trip_students if ts.parada_id is not None}
    alunos = {a.id: a for a in db.scalars(select(Aluno).where(Aluno.id.in_(aluno_ids)))} if aluno_ids else {}
    paradas = {p.id: p for p in db.scalars(select(Parada).where(Parada.id.in_(parada_ids)))} if parada_ids else {}

    resultado = []
    for ts in trip_students:
        aluno = alunos.get(ts.aluno_id)
        parada = paradas.get(ts.parada_id) if ts.parada_id is not None else None
        resultado.append(
            TripStudentOut(
                id=ts.id, viagem_id=ts.viagem_id, aluno_id=ts.aluno_id, parada_id=ts.parada_id,
                ordem=ts.ordem, estado=ts.estado, chegou_em=ts.chegou_em, checkin_em=ts.checkin_em,
                checkout_em=ts.checkout_em, ausente_em=ts.ausente_em,
                aluno_nome=aluno.nome if aluno else "?", parada_endereco=parada.endereco if parada else None,
            )
        )
    return resultado


def _trip_student_out(db: Session, trip_student: TripStudent) -> TripStudentOut:
    return _trip_students_out(db, [trip_student])[0]


def _evento_ja_processado(db: Session, event_id: uuid.UUID) -> TripStudent | None:
    """Idempotência da fila offline (Bloco B4): um reenvio com o mesmo
    `event_id` não reprocessa a máquina de estados — devolve o `trip_student`
    já atualizado pelo evento original."""
    evento = db.scalars(select(EventoAluno).where(EventoAluno.event_id == event_id)).first()
    if evento is None:
        return None
    return db.get(TripStudent, evento.trip_student_id)


# ---------------------------------------------------------------------------
# Viagens — criação, listagem, ciclo de vida
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ViagemOut])
def listar_viagens(
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[ViagemOut]:
    stmt = select(Viagem).order_by(Viagem.data.desc())
    if user.role != UserRole.ADMIN:
        motorista = db.scalars(select(Motorista).where(Motorista.user_id == user.id)).first()
        if motorista is None:
            return []
        stmt = stmt.where(Viagem.motorista_id == motorista.id)
    return _viagens_out(db, list(db.scalars(stmt)))


@router.post("", response_model=ViagemOut, status_code=status.HTTP_201_CREATED)
def criar_viagem(
    payload: ViagemCreate,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> ViagemOut:
    _validar_rota(db, payload.rota_id)
    _validar_veiculo(db, payload.veiculo_id)
    _validar_motorista(db, payload.motorista_id)

    viagem = Viagem(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return _viagem_out(db, viagem)


@router.get("/{viagem_id}", response_model=ViagemOut)
def obter_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> ViagemOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    return _viagem_out(db, viagem)


@router.post("/{viagem_id}/iniciar", response_model=ViagemOut)
def iniciar_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> ViagemOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)

    alunos_paradas = list(
        db.execute(
            select(Aluno.id, Parada.id, Parada.ordem_base)
            .join(Parada, Aluno.parada_id == Parada.id)
            .where(Parada.rota_id == viagem.rota_id, Aluno.ativo.is_(True))
            .order_by(Parada.ordem_base)
        ).all()
    )

    try:
        novos_trip_students = tsm.iniciar_viagem(viagem, alunos_paradas, ocorrido_em=_now())
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    db.add_all(novos_trip_students)
    db.commit()
    db.refresh(viagem)
    return _viagem_out(db, viagem)


@router.post("/{viagem_id}/finalizar", response_model=ViagemOut)
def finalizar_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> ViagemOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    trip_students = _listar_trip_students(db, viagem)

    try:
        tsm.finalizar_viagem(viagem, trip_students, ocorrido_em=_now())
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    db.commit()
    db.refresh(viagem)
    return _viagem_out(db, viagem)


@router.post("/{viagem_id}/estou-atrasado", response_model=ViagemOut)
def estou_atrasado(
    viagem_id: uuid.UUID,
    payload: EstouAtrasadoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> ViagemOut:
    """Botão "Estou atrasado" (CLAUDE.md §5): empurra a cauda manualmente e
    reagenda os avisos de preparo pendentes — não é o mesmo que
    `atraso_acumulado_segundos` (só diagnóstico, ver `app/models/viagem.py`).
    """
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    if viagem.status != ViagemStatus.EM_ANDAMENTO:
        raise _mapear_erro_dominio(
            ViagemStatusInvalidoError(viagem.status, ViagemStatus.EM_ANDAMENTO, "estou_atrasado")
        )

    todos = _listar_trip_students(db, viagem)
    pos_evento.processar_estou_atrasado(db, viagem, todos, payload.minutos, _now())

    db.commit()
    db.refresh(viagem)
    return _viagem_out(db, viagem)


# ---------------------------------------------------------------------------
# Trip students — leitura e reordenação
# ---------------------------------------------------------------------------


@router.get("/{viagem_id}/trip-students", response_model=list[TripStudentOut])
def listar_trip_students(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[TripStudentOut]:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    return _trip_students_out(db, _listar_trip_students(db, viagem))


@router.patch("/{viagem_id}/trip-students/reordenar", response_model=list[TripStudentOut])
def reordenar_trip_students(
    viagem_id: uuid.UUID,
    payload: ReordenarRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[TripStudentOut]:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    nova_ordem = {item.trip_student_id: item.ordem for item in payload.itens}

    alvo = list(
        db.scalars(
            select(TripStudent).where(
                TripStudent.viagem_id == viagem.id, TripStudent.id.in_(nova_ordem.keys())
            )
        )
    )

    try:
        tsm.reordenar(viagem, alvo, nova_ordem)
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    todos = _listar_trip_students(db, viagem)
    pos_evento.processar_reordenar(db, viagem, todos, alvo, _now())

    db.commit()
    return _trip_students_out(db, sorted(alvo, key=lambda ts: ts.ordem))


# ---------------------------------------------------------------------------
# Eventos do aluno — Cheguei / Checkin / Checkout / Ausente / Desfazer
# ---------------------------------------------------------------------------


_POS_EVENTO_POR_TIPO = {
    EventoAlunoTipo.CHEGUEI: pos_evento.processar_cheguei,
    EventoAlunoTipo.CHECKIN: pos_evento.processar_checkin,
    EventoAlunoTipo.CHECKOUT: pos_evento.processar_checkout,
    EventoAlunoTipo.AUSENTE: pos_evento.processar_ausente,
    EventoAlunoTipo.DESFAZER_CHEGADA: pos_evento.processar_desfazer_chegada,
    EventoAlunoTipo.DESFAZER_CHECKIN: pos_evento.processar_desfazer_checkin,
}


def _registrar_evento(
    db: Session,
    viagem: Viagem,
    trip_student: TripStudent,
    evento: EventoAluno,
    trip_students_ordenados: list[TripStudent],
    *,
    registrar_amostra: bool = True,
) -> TripStudent:
    """Persiste o evento + motor de tempos/notificações (Bloco B3) na mesma
    transação. Bloco B4: se o `event_id` perder uma corrida contra um POST
    concorrente idêntico (índice único de `0008_reconciliacao_temporal`), a
    `IntegrityError` vira uma resposta idempotente (o estado do vencedor) em
    vez de um 500 — a fila offline pode reenviar com segurança.
    """
    db.add(evento)
    try:
        extra: dict = {}
        if evento.tipo == EventoAlunoTipo.CHEGUEI:
            extra["registrar_amostra"] = registrar_amostra
        # Bloco B5: só CHEGUEI (chegada/iminência imediatas) e CHECKIN/AUSENTE
        # (sinal de dismiss da notificação persistente) falam com o push de
        # verdade — os outros tipos de evento não enviam nada, sender ocioso
        # seria só overhead de assinatura.
        if evento.tipo in (EventoAlunoTipo.CHEGUEI, EventoAlunoTipo.CHECKIN, EventoAlunoTipo.AUSENTE):
            extra["sender"] = build_sender(db)
        _POS_EVENTO_POR_TIPO[evento.tipo](db, viagem, trip_students_ordenados, trip_student, evento.ocorrido_em, **extra)
        db.commit()
    except IntegrityError:
        db.rollback()
        vencedor = _evento_ja_processado(db, evento.event_id)
        if vencedor is None:
            raise
        return vencedor
    db.refresh(trip_student)
    return trip_student


def _reconciliar_evento(viagem: Viagem, payload: EventoAlunoRequest, agora_servidor: datetime.datetime):
    return reconciliar(
        device_timestamp=payload.device_timestamp,
        device_enviado_em=payload.device_enviado_em,
        agora_servidor=agora_servidor,
        nao_antes_de=viagem.iniciada_em,
    )


@router.post("/{viagem_id}/trip-students/{trip_student_id}/cheguei", response_model=TripStudentOut)
def marcar_cheguei(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.registrar_cheguei(
            viagem, alvo, outros, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros, registrar_amostra=reconciliado.confiavel)
    return _trip_student_out(db, resultado)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/checkin", response_model=TripStudentOut)
def marcar_checkin(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.registrar_checkin(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros)
    return _trip_student_out(db, resultado)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/checkout", response_model=TripStudentOut)
def marcar_checkout(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.registrar_checkout(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros)
    return _trip_student_out(db, resultado)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/ausente", response_model=TripStudentOut)
def marcar_ausente(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.registrar_ausente(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros)
    return _trip_student_out(db, resultado)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/desfazer-chegada", response_model=TripStudentOut)
def desfazer_chegada(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.desfazer_chegada(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros)
    return _trip_student_out(db, resultado)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/desfazer-checkin", response_model=TripStudentOut)
def desfazer_checkin(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudentOut:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    ja_processado = _evento_ja_processado(db, payload.event_id)
    if ja_processado is not None:
        return _trip_student_out(db, ja_processado)

    outros = _listar_trip_students(db, viagem)
    agora_servidor = _now()
    reconciliado = _reconciliar_evento(viagem, payload, agora_servidor)

    try:
        evento = tsm.desfazer_checkin(
            viagem, alvo, ocorrido_em=reconciliado.ocorrido_em, registrado_em=agora_servidor,
            device_timestamp=payload.device_timestamp, event_id=payload.event_id, registrado_por=user.id,
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    resultado = _registrar_evento(db, viagem, alvo, evento, outros)
    return _trip_student_out(db, resultado)
