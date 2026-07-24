"""Tenant (dados próprios) + onboarding: aceite do DPA/LGPD (Sprint 1).

Não há listagem/criação de tenants aqui — o provisionamento acontece fora do
fluxo normal da API (Sprint 0). O que o painel do gestor precisa é:
  - ver e editar os dados do próprio tenant (`GET/PATCH /api/tenants/me`)
  - registrar e consultar o aceite do DPA (`/api/tenants/me/consentimentos`)

`Consentimento` é escopado por tenant (via `TenantMixin` + RLS), então
`get_tenant_db` já garante que cada tenant só vê os próprios registros.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_tenant_db, require_role
from app.models.consentimento import Consentimento
from app.models.tenant import Tenant
from app.schemas.cadastros import (
    ConsentimentoCreate,
    ConsentimentoOut,
    TenantOut,
    TenantUpdate,
)

router = APIRouter(prefix="/api/tenants", tags=["cadastros:tenants"])

_TENANT_NAO_ENCONTRADO = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant não encontrado.")

# Versão vigente do DPA — usada para sinalizar quando um novo aceite é exigido
# (ex.: após atualização dos termos). Mantido aqui por simplicidade no Sprint 1;
# pode migrar para configuração/feature flag quando o fluxo de versionamento
# do DPA for desenhado (Sprint 6 — hardening/LGPD).
DPA_VERSAO_ATUAL = "1.0"


def _get_tenant_or_404(db: Session, tenant_id) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise _TENANT_NAO_ENCONTRADO
    return tenant


# ---------------------------------------------------------------------------
# Tenant — dados próprios
# ---------------------------------------------------------------------------


@router.get("/me", response_model=TenantOut)
def obter_meu_tenant(
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Tenant:
    return _get_tenant_or_404(db, user.tenant_id)


@router.patch("/me", response_model=TenantOut)
def atualizar_meu_tenant(
    payload: TenantUpdate,
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Tenant:
    tenant = _get_tenant_or_404(db, user.tenant_id)
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, campo, valor)
    db.commit()
    db.refresh(tenant)
    return tenant


# ---------------------------------------------------------------------------
# Onboarding — aceite do DPA (LGPD)
# ---------------------------------------------------------------------------


@router.get("/me/consentimentos", response_model=list[ConsentimentoOut])
def listar_consentimentos(
    db: Session = Depends(get_tenant_db),
    _user=Depends(require_role("admin")),
) -> list[Consentimento]:
    return list(
        db.scalars(
            select(Consentimento)
            .where(Consentimento.tipo == "dpa")
            .order_by(Consentimento.created_at.desc())
        )
    )


@router.get("/me/consentimentos/status")
def status_consentimento_dpa(
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> dict:
    """Resumo usado pelo painel para decidir se deve bloquear o tenant até o
    aceite: se não há aceite registrado para a versão vigente, `pendente=True`."""
    aceite_vigente = db.scalar(
        select(Consentimento)
        .where(Consentimento.tipo == "dpa", Consentimento.versao == DPA_VERSAO_ATUAL)
        .order_by(Consentimento.created_at.desc())
        .limit(1)
    )
    return {
        "tenant_id": user.tenant_id,
        "versao_atual": DPA_VERSAO_ATUAL,
        "pendente": aceite_vigente is None,
        "ultimo_aceite": ConsentimentoOut.model_validate(aceite_vigente) if aceite_vigente else None,
    }


@router.post("/me/consentimentos", response_model=ConsentimentoOut, status_code=status.HTTP_201_CREATED)
def registrar_aceite_dpa(
    payload: ConsentimentoCreate,
    db: Session = Depends(get_tenant_db),
    user=Depends(require_role("admin")),
) -> Consentimento:
    consentimento = Consentimento(
        tenant_id=user.tenant_id,
        tipo="dpa",
        versao=payload.versao,
        aceito_por_user_id=user.id,
    )
    db.add(consentimento)
    db.commit()
    db.refresh(consentimento)
    return consentimento
