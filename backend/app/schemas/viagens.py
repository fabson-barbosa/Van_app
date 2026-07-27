"""Schemas Pydantic do motor de viagem (Bloco B2 — CLAUDE.md §4/§9).

Convenções: mesmas do `schemas/cadastros.py` (`*Create`/`*Update` de entrada,
`*Out` com `from_attributes=True` de saída).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.trip_student import TripStudentEstado
from app.models.viagem import ViagemStatus

# ---------------------------------------------------------------------------
# Viagem
# ---------------------------------------------------------------------------


class ViagemCreate(BaseModel):
    rota_id: uuid.UUID
    veiculo_id: uuid.UUID
    motorista_id: uuid.UUID
    data: date


class ViagemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    rota_id: uuid.UUID
    veiculo_id: uuid.UUID
    motorista_id: uuid.UUID
    data: date
    status: ViagemStatus
    iniciada_em: datetime | None
    finalizada_em: datetime | None
    atraso_acumulado_segundos: int
    varredura_confirmada: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# TripStudent
# ---------------------------------------------------------------------------


class TripStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    viagem_id: uuid.UUID
    aluno_id: uuid.UUID
    parada_id: uuid.UUID | None
    ordem: int
    estado: TripStudentEstado
    chegou_em: datetime | None
    checkin_em: datetime | None
    checkout_em: datetime | None
    ausente_em: datetime | None


# ---------------------------------------------------------------------------
# Eventos — payload de entrada comum a Cheguei/Checkin/Checkout/Ausente/...
# ---------------------------------------------------------------------------


class EventoAlunoRequest(BaseModel):
    """`device_timestamp` é opcional — cobre o caso de fila offline (§4/§8),
    em que o app reenvia eventos gerados enquanto sem sinal."""

    device_timestamp: datetime | None = None


# ---------------------------------------------------------------------------
# "Estou atrasado" (CLAUDE.md §5 — empurra a cauda manualmente)
# ---------------------------------------------------------------------------


class EstouAtrasadoRequest(BaseModel):
    minutos: int = Field(gt=0, description="Minutos a empurrar a cauda da rota — sempre positivo.")


# ---------------------------------------------------------------------------
# Reordenação (CLAUDE.md §8 — só alunos ainda em 'aguardando')
# ---------------------------------------------------------------------------


class ReordenarItem(BaseModel):
    trip_student_id: uuid.UUID
    ordem: int = Field(ge=0)


class ReordenarRequest(BaseModel):
    itens: list[ReordenarItem] = Field(min_length=1)
