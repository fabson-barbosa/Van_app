"""CRUD de alunos e responsáveis — vínculo aluno ↔ parada ↔ responsável (Sprint 1).

`Aluno` e `Responsavel` são escopados por tenant (via `TenantMixin` + RLS —
ver migration 0003_rls_paradas_responsaveis para `Responsavel`). Ainda assim
toda operação em responsável primeiro carrega o aluno e valida o vínculo,
para devolver 404 em vez de vazar erro de FK.

`parada_id` (em `Aluno`) e `user_id` (em `Responsavel`) referenciam outras
tabelas com RLS própria — validamos a existência explicitamente para devolver
404 (em vez de deixar a FK estourar 500), sem vazar dados de outro tenant.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.aluno import Aluno, Responsavel
from app.models.rota import Parada
from app.models.user import User
from app.schemas.cadastros import (
    AlunoCreate,
    AlunoOut,
    AlunoUpdate,
    ResponsavelCreate,
    ResponsavelOut,
    ResponsavelUpdate,
)

router = APIRouter(prefix="/api/alunos", tags=["cadastros:alunos"])

_ALUNO_NAO_ENCONTRADO = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aluno não encontrado.")
_RESPONSAVEL_NAO_ENCONTRADO = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responsável não encontrado.")
_PARADA_INVALIDA = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parada não encontrada para este tenant.")
_USER_INVALIDO = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado para este tenant.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_aluno_or_404(db: Session, aluno_id: uuid.UUID) -> Aluno:
    aluno = db.get(Aluno, aluno_id)
    if aluno is None:
        raise _ALUNO_NAO_ENCONTRADO
    return aluno


def _get_responsavel_or_404(db: Session, aluno: Aluno, responsavel_id: uuid.UUID) -> Responsavel:
    responsavel = db.get(Responsavel, responsavel_id)
    if responsavel is None or responsavel.aluno_id != aluno.id:
        raise _RESPONSAVEL_NAO_ENCONTRADO
    return responsavel


def _validar_parada(db: Session, parada_id: uuid.UUID | None) -> None:
    """`parada_id` é opcional; quando informado, precisa pertencer ao tenant
    (RLS própria de `paradas` cuida disso — `db.get` só acha paradas do
    tenant atual)."""
    if parada_id is not None and db.get(Parada, parada_id) is None:
        raise _PARADA_INVALIDA


def _validar_user(db: Session, user_id: uuid.UUID) -> None:
    if db.get(User, user_id) is None:
        raise _USER_INVALIDO


# ---------------------------------------------------------------------------
# Alunos
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AlunoOut])
def listar_alunos(
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[Aluno]:
    return list(db.scalars(select(Aluno).order_by(Aluno.nome)))


@router.post("", response_model=AlunoOut, status_code=status.HTTP_201_CREATED)
def criar_aluno(
    payload: AlunoCreate,
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Aluno:
    _validar_parada(db, payload.parada_id)
    aluno = Aluno(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(aluno)
    db.commit()
    db.refresh(aluno)
    return aluno


@router.get("/{aluno_id}", response_model=AlunoOut)
def obter_aluno(
    aluno_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Aluno:
    return _get_aluno_or_404(db, aluno_id)


@router.patch("/{aluno_id}", response_model=AlunoOut)
def atualizar_aluno(
    aluno_id: uuid.UUID,
    payload: AlunoUpdate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Aluno:
    aluno = _get_aluno_or_404(db, aluno_id)
    dados = payload.model_dump(exclude_unset=True)
    if "parada_id" in dados:
        _validar_parada(db, dados["parada_id"])
    for campo, valor in dados.items():
        setattr(aluno, campo, valor)
    db.commit()
    db.refresh(aluno)
    return aluno


@router.delete("/{aluno_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_aluno(
    aluno_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> None:
    aluno = _get_aluno_or_404(db, aluno_id)
    db.delete(aluno)  # cascade remove responsáveis (ondelete="CASCADE" na FK)
    db.commit()


# ---------------------------------------------------------------------------
# Responsáveis (aninhados em /api/alunos/{aluno_id}/responsaveis)
# ---------------------------------------------------------------------------


@router.get("/{aluno_id}/responsaveis", response_model=list[ResponsavelOut])
def listar_responsaveis(
    aluno_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[Responsavel]:
    aluno = _get_aluno_or_404(db, aluno_id)
    return list(db.scalars(select(Responsavel).where(Responsavel.aluno_id == aluno.id)))


@router.post("/{aluno_id}/responsaveis", response_model=ResponsavelOut, status_code=status.HTTP_201_CREATED)
def criar_responsavel(
    aluno_id: uuid.UUID,
    payload: ResponsavelCreate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Responsavel:
    aluno = _get_aluno_or_404(db, aluno_id)
    if payload.aluno_id != aluno.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="aluno_id do payload precisa corresponder ao aluno da URL.",
        )
    _validar_user(db, payload.user_id)
    responsavel = Responsavel(tenant_id=aluno.tenant_id, **payload.model_dump())
    db.add(responsavel)
    db.commit()
    db.refresh(responsavel)
    return responsavel


@router.get("/{aluno_id}/responsaveis/{responsavel_id}", response_model=ResponsavelOut)
def obter_responsavel(
    aluno_id: uuid.UUID,
    responsavel_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Responsavel:
    aluno = _get_aluno_or_404(db, aluno_id)
    return _get_responsavel_or_404(db, aluno, responsavel_id)


@router.patch("/{aluno_id}/responsaveis/{responsavel_id}", response_model=ResponsavelOut)
def atualizar_responsavel(
    aluno_id: uuid.UUID,
    responsavel_id: uuid.UUID,
    payload: ResponsavelUpdate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Responsavel:
    aluno = _get_aluno_or_404(db, aluno_id)
    responsavel = _get_responsavel_or_404(db, aluno, responsavel_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(responsavel, campo, valor)
    db.commit()
    db.refresh(responsavel)
    return responsavel


@router.delete("/{aluno_id}/responsaveis/{responsavel_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_responsavel(
    aluno_id: uuid.UUID,
    responsavel_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> None:
    aluno = _get_aluno_or_404(db, aluno_id)
    responsavel = _get_responsavel_or_404(db, aluno, responsavel_id)
    db.delete(responsavel)
    db.commit()
