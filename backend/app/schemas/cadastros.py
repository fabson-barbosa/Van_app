"""Schemas Pydantic dos cadastros do Sprint 1.

Hierarquia coberta (arquitetura.md, seção 5):
    Tenant -> Veículos / Rotas -> Paradas -> Alunos -> Responsáveis

Convenções:
- `*Create` / `*Update`: payloads de entrada (Update com campos opcionais —
  PATCH parcial).
- `*Out`: payloads de saída, com `model_config = {"from_attributes": True}`
  para serializar diretamente a partir dos models SQLAlchemy.
- Campos `tenant_id`/timestamps não entram em Create/Update — são geridos
  pela API (RLS via `app.tenant_id`) e pelo banco.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Veículos
# ---------------------------------------------------------------------------


class VeiculoBase(BaseModel):
    placa: str = Field(min_length=1, max_length=20)
    modelo: str | None = None
    capacidade: int | None = Field(default=None, ge=0)
    km_atual: int = Field(default=0, ge=0)


class VeiculoCreate(VeiculoBase):
    pass


class VeiculoUpdate(BaseModel):
    placa: str | None = Field(default=None, min_length=1, max_length=20)
    modelo: str | None = None
    capacidade: int | None = Field(default=None, ge=0)
    km_atual: int | None = Field(default=None, ge=0)


class VeiculoOut(VeiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


class RotaBase(BaseModel):
    nome: str = Field(min_length=1)
    turno: str = Field(min_length=1, max_length=20)
    escola: str | None = None
    ativa: bool = True


class RotaCreate(RotaBase):
    pass


class RotaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    turno: str | None = Field(default=None, min_length=1, max_length=20)
    escola: str | None = None
    ativa: bool | None = None


class RotaOut(RotaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Paradas (a coluna `geo` é PostGIS; expomos lat/lon, que a API converte)
# ---------------------------------------------------------------------------


class ParadaBase(BaseModel):
    nome: str | None = None
    endereco: str | None = None
    ordem_base: int = Field(ge=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    # "Estimativa do motorista" (CLAUDE.md §5) — semente do trajeto que
    # termina nesta parada. Nula até alguém informar; `leg_duration.py` usa
    # 240s como padrão enquanto isso (ver docstring de `Parada`).
    duracao_estimada_segundos: int | None = Field(default=None, ge=0)


class ParadaCreate(ParadaBase):
    pass


class ParadaUpdate(BaseModel):
    nome: str | None = None
    endereco: str | None = None
    ordem_base: int | None = Field(default=None, ge=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    duracao_estimada_segundos: int | None = Field(default=None, ge=0)


class ParadaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rota_id: uuid.UUID
    nome: str | None
    endereco: str | None
    ordem_base: int
    latitude: float
    longitude: float
    duracao_estimada_segundos: int | None
    ativo: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Alunos
# ---------------------------------------------------------------------------


class AlunoBase(BaseModel):
    nome: str = Field(min_length=1)
    parada_id: uuid.UUID | None = None
    dados_medicos: str | None = None
    ativo: bool = True


class AlunoCreate(AlunoBase):
    pass


class AlunoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    parada_id: uuid.UUID | None = None
    dados_medicos: str | None = None
    ativo: bool | None = None


class AlunoOut(AlunoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Responsáveis (vínculo aluno <-> usuário responsável)
# ---------------------------------------------------------------------------


class ResponsavelBase(BaseModel):
    aluno_id: uuid.UUID
    user_id: uuid.UUID
    parentesco: str | None = None
    permissoes: dict = Field(default_factory=dict)


class ResponsavelCreate(ResponsavelBase):
    pass


class ResponsavelUpdate(BaseModel):
    parentesco: str | None = None
    permissoes: dict | None = None


class ResponsavelOut(ResponsavelBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ativo: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Tenant (edição dos próprios dados — criação acontece no provisionamento)
# ---------------------------------------------------------------------------


class TenantUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1)
    plano: str | None = None
    status_billing: str | None = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    plano: str
    status_billing: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Onboarding — aceite do DPA (LGPD)
# ---------------------------------------------------------------------------


class ConsentimentoCreate(BaseModel):
    """Payload para registrar o aceite — só a versão precisa ser informada;
    tipo, tenant e usuário são preenchidos pela API a partir do contexto."""

    versao: str = Field(min_length=1, max_length=20)


class ConsentimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    tipo: str
    versao: str
    aceito_por_user_id: uuid.UUID | None
    created_at: datetime
