"""Endpoints do app Responsável (Bloco B5, CLAUDE.md §2/§5/§10).

Cada endpoint é escopado ao usuário autenticado via o vínculo
`Responsavel.user_id == current_user.id` — nunca por `aluno_id` cru vindo da
URL. Um responsável só enxerga os PRÓPRIOS filhos: nenhuma consulta aqui
devolve dado de outro aluno, a lista completa de uma rota, posição
geográfica ou `dados_medicos` (minimização de dados, mesma postura do B4
para o motorista — ver PROGRESSO.md).

Mapa "virtual": progresso por PARADA (quantas faltam, faixa de minutos),
nunca coordenada — CLAUDE.md §2/§10 não têm GPS nesta versão. A matemática é
a mesma do motor de tempos do B3 (`app/services/pos_evento.py::calcular_progresso_aluno`),
só que consultada sob demanda em vez de disparar push.
"""
import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.aluno import Aluno, Responsavel
from app.models.evento_aluno import EventoAluno, EventoAlunoTipo
from app.models.rota import Parada
from app.models.trip_student import TripStudent, TripStudentEstado
from app.models.viagem import Viagem, ViagemStatus
from app.schemas.auth import CurrentUser
from app.schemas.responsavel import EventoHistoricoOut, FilhoOut, StatusFilhoOut
from app.services import pos_evento

router = APIRouter(prefix="/api/responsavel", tags=["responsavel"])

_ALUNO_NAO_ENCONTRADO = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aluno não encontrado.")

# Só os eventos que descrevem a realidade final do aluno — as duas transições
# de "desfazer" são correção interna, não fato relevante pro responsável ver
# (CLAUDE.md §4: desfazer chegada explicitamente "não dispara notificação de
# correção", mesmo espírito vale pro histórico).
_TIPOS_HISTORICO = (
    EventoAlunoTipo.CHEGUEI, EventoAlunoTipo.CHECKIN, EventoAlunoTipo.CHECKOUT, EventoAlunoTipo.AUSENTE,
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _get_aluno_autorizado(db: Session, aluno_id: uuid.UUID, user: CurrentUser) -> Aluno:
    # Vínculo e aluno precisam estar ativos (achado A3): um responsável ou
    # aluno soft-deleted não concede/expõe mais acesso.
    vinculo = db.scalars(
        select(Responsavel).where(
            Responsavel.user_id == user.id, Responsavel.aluno_id == aluno_id, Responsavel.ativo.is_(True)
        )
    ).first()
    if vinculo is None:
        raise _ALUNO_NAO_ENCONTRADO
    aluno = db.get(Aluno, aluno_id)
    if aluno is None or not aluno.ativo:
        raise _ALUNO_NAO_ENCONTRADO
    return aluno


def _viagem_do_dia(db: Session, aluno: Aluno, dia: datetime.date) -> tuple[Viagem, TripStudent] | None:
    """`None` cobre TODOS os casos de "sem dado pra hoje": aluno sem parada
    cadastrada, rota sem viagem nesta data, ou aluno fora do gabarito da
    viagem (inativo no momento em que a viagem foi montada)."""
    if aluno.parada_id is None:
        return None
    parada = db.get(Parada, aluno.parada_id)
    if parada is None:
        return None
    viagem = db.scalars(select(Viagem).where(Viagem.rota_id == parada.rota_id, Viagem.data == dia)).first()
    if viagem is None:
        return None
    trip_student = db.scalars(
        select(TripStudent).where(TripStudent.viagem_id == viagem.id, TripStudent.aluno_id == aluno.id)
    ).first()
    if trip_student is None:
        return None
    return viagem, trip_student


@router.get("/filhos", response_model=list[FilhoOut])
def listar_filhos(
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role("responsavel")),
) -> list[FilhoOut]:
    vinculos = db.scalars(
        select(Responsavel).where(Responsavel.user_id == user.id, Responsavel.ativo.is_(True))
    ).all()
    aluno_ids = {v.aluno_id for v in vinculos}
    if not aluno_ids:
        return []

    alunos = {
        a.id: a for a in db.scalars(select(Aluno).where(Aluno.id.in_(aluno_ids), Aluno.ativo.is_(True)))
    }
    parada_ids = {a.parada_id for a in alunos.values() if a.parada_id is not None}
    paradas = {p.id: p for p in db.scalars(select(Parada).where(Parada.id.in_(parada_ids)))} if parada_ids else {}

    resultado = []
    for aluno_id in aluno_ids:
        aluno = alunos.get(aluno_id)
        if aluno is None:
            continue
        parada = paradas.get(aluno.parada_id) if aluno.parada_id is not None else None
        resultado.append(FilhoOut(aluno_id=aluno.id, nome=aluno.nome, parada_endereco=parada.endereco if parada else None))
    return resultado


@router.get("/filhos/{aluno_id}/status", response_model=StatusFilhoOut)
def status_filho(
    aluno_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role("responsavel")),
) -> StatusFilhoOut:
    aluno = _get_aluno_autorizado(db, aluno_id, user)
    achado = _viagem_do_dia(db, aluno, datetime.date.today())
    if achado is None:
        return StatusFilhoOut(aluno_id=aluno.id, tem_viagem_hoje=False)
    viagem, trip_student = achado

    if viagem.status != ViagemStatus.EM_ANDAMENTO:
        # Planejada (ainda não saiu da garagem) ou finalizada — sem cauda pra
        # projetar, só o estado bruto do aluno.
        return StatusFilhoOut(
            aluno_id=aluno.id, tem_viagem_hoje=True, viagem_status=viagem.status.value, estado=trip_student.estado,
            chegou_em=trip_student.chegou_em if trip_student.estado == TripStudentEstado.CHEGOU else None,
        )

    todos = list(
        db.scalars(select(TripStudent).where(TripStudent.viagem_id == viagem.id).order_by(TripStudent.ordem))
    )
    progresso = pos_evento.calcular_progresso_aluno(db, viagem, todos, trip_student, _now())
    return StatusFilhoOut(
        aluno_id=aluno.id, tem_viagem_hoje=True, viagem_status=viagem.status.value, estado=progresso.estado,
        paradas_totais=progresso.paradas_totais, paradas_concluidas=progresso.paradas_concluidas,
        paradas_restantes=progresso.paradas_restantes, faixa_min_baixo=progresso.faixa_min_baixo,
        faixa_min_alto=progresso.faixa_min_alto, chegou_em=progresso.chegou_em,
    )


@router.get("/filhos/{aluno_id}/historico", response_model=list[EventoHistoricoOut])
def historico_filho(
    aluno_id: uuid.UUID,
    data: datetime.date | None = None,
    db: Session = Depends(get_tenant_db),
    user: CurrentUser = Depends(require_role("responsavel")),
) -> list[EventoHistoricoOut]:
    aluno = _get_aluno_autorizado(db, aluno_id, user)
    achado = _viagem_do_dia(db, aluno, data or datetime.date.today())
    if achado is None:
        return []
    _viagem, trip_student = achado

    eventos = db.scalars(
        select(EventoAluno)
        .where(EventoAluno.trip_student_id == trip_student.id, EventoAluno.tipo.in_(_TIPOS_HISTORICO))
        .order_by(EventoAluno.ocorrido_em)
    ).all()
    return [EventoHistoricoOut(tipo=e.tipo.value, ocorrido_em=e.ocorrido_em) for e in eventos]
