"""CRUD de veículos — cadastro de frota do tenant (Sprint 1).

Escopo de acesso: painel do gestor (role `admin`), conforme o protótipo
`03-app-gestor.html`. Toda query passa por `get_tenant_db`, que já fixa
`app.tenant_id` na sessão — a política de RLS garante o isolamento entre
tenants (não precisamos filtrar por tenant_id manualmente nas queries).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.veiculo import Veiculo
from app.schemas.cadastros import VeiculoCreate, VeiculoOut, VeiculoUpdate

router = APIRouter(prefix="/api/veiculos", tags=["cadastros:veiculos"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veículo não encontrado.")


def _get_or_404(db: Session, veiculo_id: uuid.UUID) -> Veiculo:
    veiculo = db.get(Veiculo, veiculo_id)
    if veiculo is None:
        raise _NOT_FOUND
    return veiculo


@router.get("", response_model=list[VeiculoOut])
def listar_veiculos(
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[Veiculo]:
    return list(db.scalars(select(Veiculo).order_by(Veiculo.placa)))


@router.post("", response_model=VeiculoOut, status_code=status.HTTP_201_CREATED)
def criar_veiculo(
    payload: VeiculoCreate,
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Veiculo:
    veiculo = Veiculo(tenant_id=user.tenant_id, **payload.model_dump())
    db.add(veiculo)
    db.commit()
    db.refresh(veiculo)
    return veiculo


@router.get("/{veiculo_id}", response_model=VeiculoOut)
def obter_veiculo(
    veiculo_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Veiculo:
    return _get_or_404(db, veiculo_id)


@router.patch("/{veiculo_id}", response_model=VeiculoOut)
def atualizar_veiculo(
    veiculo_id: uuid.UUID,
    payload: VeiculoUpdate,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> Veiculo:
    veiculo = _get_or_404(db, veiculo_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(veiculo, campo, valor)
    db.commit()
    db.refresh(veiculo)
    return veiculo


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_veiculo(
    veiculo_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> None:
    veiculo = _get_or_404(db, veiculo_id)
    db.delete(veiculo)
    db.commit()
