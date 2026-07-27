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
    # Enriquecido para o app do Motorista (Bloco B4) — evita um segundo round-trip
    # a `/api/rotas/{id}` (admin-only; o motorista não tem esse acesso, ver
    # PROGRESSO.md B4). Preenchido por join em `api/viagens.py`, não persistido.
    rota_nome: str
    rota_turno: str
    rota_escola: str | None
    total_alunos: int


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
    # Enriquecido para o app do Motorista (Bloco B4): `/api/alunos` e
    # `/api/rotas/{id}/paradas` são admin-only (minimização de dados, LGPD —
    # ver PROGRESSO.md B4), então o motorista não tem outra forma de ver o
    # nome do aluno ou o endereço da parada, ambos exigidos pelo diálogo do
    # Cheguei (CLAUDE.md §6). `parada_endereco` é o texto livre de
    # `Parada.endereco`, sem parsing — heurística de logradouro/número erraria
    # em endereços atípicos, e o diálogo é exatamente onde isso mais pesa.
    # NÃO inclui `dados_medicos`.
    aluno_nome: str
    parada_endereco: str | None


# ---------------------------------------------------------------------------
# Eventos — payload de entrada comum a Cheguei/Checkin/Checkout/Ausente/...
# ---------------------------------------------------------------------------


class EventoAlunoRequest(BaseModel):
    """Bloco B4 — reconciliação de relógio + idempotência da fila offline (§4/§8).

    `device_timestamp`/`device_enviado_em` alimentam
    `app/services/reconciliacao.py` (o instante RECONCILIADO do evento — sem
    os dois, cai no relógio do servidor, comportamento anterior ao B4).
    `event_id` é gerado no aparelho no momento do toque e reenviado sem
    trocar em cada tentativa da fila offline — é a chave de idempotência:
    reenviar o mesmo `event_id` nunca grava um segundo evento, devolve o
    estado atual em vez de 409.
    """

    device_timestamp: datetime | None = None
    device_enviado_em: datetime | None = None
    event_id: uuid.UUID


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
