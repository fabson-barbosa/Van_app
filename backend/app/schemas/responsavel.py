"""Schemas do app Responsável (Bloco B5) — minimização de dados (LGPD, mesma
postura do B4): nunca `dados_medicos`, nunca coordenada/GPS, nunca a lista
completa da rota (só a posição relativa do PRÓPRIO filho)."""
from __future__ import annotations

import datetime
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.trip_student import TripStudentEstado


class FilhoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    aluno_id: uuid.UUID
    nome: str
    parada_endereco: str | None


class StatusFilhoOut(BaseModel):
    """Mapa VIRTUAL (CLAUDE.md §2/§10) — progresso por PARADA, nunca
    coordenada. `faixa_min_*` nunca é minuto exato (CLAUDE.md §5)."""

    aluno_id: uuid.UUID
    tem_viagem_hoje: bool
    viagem_status: str | None = None
    estado: TripStudentEstado | None = None
    paradas_totais: int | None = None
    paradas_concluidas: int | None = None
    paradas_restantes: int | None = None
    faixa_min_baixo: int | None = None
    faixa_min_alto: int | None = None
    chegou_em: datetime.datetime | None = None


class EventoHistoricoOut(BaseModel):
    tipo: str
    ocorrido_em: datetime.datetime
