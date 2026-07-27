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
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.aluno import Aluno
from app.models.evento_aluno import EventoAluno
from app.models.motorista import Motorista
from app.models.rota import Parada, Rota
from app.models.trip_student import TripStudent
from app.models.user import UserRole
from app.models.veiculo import Veiculo
from app.models.viagem import Viagem
from app.schemas.auth import CurrentUser
from app.schemas.viagens import (
    EventoAlunoRequest,
    ReordenarRequest,
    TripStudentOut,
    ViagemCreate,
    ViagemOut,
)
from app.services import trip_state_machine as tsm
from app.services.exceptions import DominioError

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


# ---------------------------------------------------------------------------
# Viagens — criação, listagem, ciclo de vida
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ViagemOut])
def listar_viagens(
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[Viagem]:
    stmt = select(Viagem).order_by(Viagem.data.desc())
    if user.role != UserRole.ADMIN:
        motorista = db.scalars(select(Motorista).where(Motorista.user_id == user.id)).first()
        if motorista is None:
            return []
        stmt = stmt.where(Viagem.motorista_id == motorista.id)
    return list(db.scalars(stmt))


@router.post("", response_model=ViagemOut, status_code=status.HTTP_201_CREATED)
def criar_viagem(
    payload: ViagemCreate,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role("admin")),
) -> Viagem:
    _validar_rota(db, payload.rota_id)
    _validar_veiculo(db, payload.veiculo_id)
    _validar_motorista(db, payload.motorista_id)

    viagem = Viagem(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(viagem)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.get("/{viagem_id}", response_model=ViagemOut)
def obter_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> Viagem:
    return _get_viagem_autorizada(db, viagem_id, user)


@router.post("/{viagem_id}/iniciar", response_model=ViagemOut)
def iniciar_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> Viagem:
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
        novos_trip_students = tsm.iniciar_viagem(viagem, alunos_paradas, now=_now())
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    db.add_all(novos_trip_students)
    db.commit()
    db.refresh(viagem)
    return viagem


@router.post("/{viagem_id}/finalizar", response_model=ViagemOut)
def finalizar_viagem(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> Viagem:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    trip_students = _listar_trip_students(db, viagem)

    try:
        tsm.finalizar_viagem(viagem, trip_students, now=_now())
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    db.commit()
    db.refresh(viagem)
    return viagem


# ---------------------------------------------------------------------------
# Trip students — leitura e reordenação
# ---------------------------------------------------------------------------


@router.get("/{viagem_id}/trip-students", response_model=list[TripStudentOut])
def listar_trip_students(
    viagem_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[TripStudent]:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    return _listar_trip_students(db, viagem)


@router.patch("/{viagem_id}/trip-students/reordenar", response_model=list[TripStudentOut])
def reordenar_trip_students(
    viagem_id: uuid.UUID,
    payload: ReordenarRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> list[TripStudent]:
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

    db.commit()
    return sorted(alvo, key=lambda ts: ts.ordem)


# ---------------------------------------------------------------------------
# Eventos do aluno — Cheguei / Checkin / Checkout / Ausente / Desfazer
# ---------------------------------------------------------------------------


def _registrar_evento(
    db: Session,
    viagem: Viagem,
    trip_student: TripStudent,
    evento: EventoAluno,
) -> TripStudent:
    db.add(evento)
    db.commit()
    db.refresh(trip_student)
    return trip_student


@router.post("/{viagem_id}/trip-students/{trip_student_id}/cheguei", response_model=TripStudentOut)
def marcar_cheguei(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)
    outros = _listar_trip_students(db, viagem)

    try:
        evento = tsm.registrar_cheguei(
            viagem, alvo, outros, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/checkin", response_model=TripStudentOut)
def marcar_checkin(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    try:
        evento = tsm.registrar_checkin(
            viagem, alvo, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/checkout", response_model=TripStudentOut)
def marcar_checkout(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    try:
        evento = tsm.registrar_checkout(
            viagem, alvo, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/ausente", response_model=TripStudentOut)
def marcar_ausente(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    try:
        evento = tsm.registrar_ausente(
            viagem, alvo, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/desfazer-chegada", response_model=TripStudentOut)
def desfazer_chegada(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    try:
        evento = tsm.desfazer_chegada(
            viagem, alvo, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)


@router.post("/{viagem_id}/trip-students/{trip_student_id}/desfazer-checkin", response_model=TripStudentOut)
def desfazer_checkin(
    viagem_id: uuid.UUID,
    trip_student_id: uuid.UUID,
    payload: EventoAlunoRequest,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role(*_PAPEIS_OPERACAO)),
) -> TripStudent:
    viagem = _get_viagem_autorizada(db, viagem_id, user)
    alvo = _get_trip_student_ou_404(db, viagem, trip_student_id)

    try:
        evento = tsm.desfazer_checkin(
            viagem, alvo, now=_now(), device_timestamp=payload.device_timestamp, registrado_por=user.id
        )
    except DominioError as exc:
        raise _mapear_erro_dominio(exc) from exc

    return _registrar_evento(db, viagem, alvo, evento)
