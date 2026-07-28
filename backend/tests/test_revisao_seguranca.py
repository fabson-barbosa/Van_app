"""Testes unitários da revisão de segurança pós-B5 (sem banco).

Cobrem os achados que dá pra travar sem Postgres:
- A1: guarda do segredo JWT no boot (`app/core/config.py`).
- A6: teto de `minutos` em "Estou atrasado" (`app/schemas/viagens.py`).

Os achados que dependem de banco (A2 trava de linha, A3 soft-delete, §11
reatribuição) estão em `tests/integration/` (rodam com `pytest -m integration`).
"""
import pytest
from pydantic import ValidationError

from app.core.config import _DEFAULT_JWT_SECRET, Settings
from app.schemas.viagens import ESTOU_ATRASADO_MAX_MINUTOS, EstouAtrasadoRequest


# ---------------------------------------------------------------------------
# A1 — segredo JWT
# ---------------------------------------------------------------------------


def test_config_rejeita_segredo_default_fora_de_development():
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret=_DEFAULT_JWT_SECRET, _env_file=None)


def test_config_rejeita_segredo_curto_fora_de_development():
    with pytest.raises(ValidationError):
        Settings(env="staging", jwt_secret="curto-demais", _env_file=None)


def test_config_aceita_segredo_default_em_development():
    # DX local: em development o placeholder é tolerado.
    s = Settings(env="development", jwt_secret=_DEFAULT_JWT_SECRET, _env_file=None)
    assert s.is_development is True


def test_config_aceita_segredo_forte_em_producao():
    s = Settings(env="production", jwt_secret="x" * 40, _env_file=None)
    assert s.is_development is False
    assert s.jwt_secret == "x" * 40


# ---------------------------------------------------------------------------
# A6 — teto de "Estou atrasado"
# ---------------------------------------------------------------------------


def test_estou_atrasado_aceita_dentro_do_teto():
    assert EstouAtrasadoRequest(minutos=30).minutos == 30
    assert EstouAtrasadoRequest(minutos=ESTOU_ATRASADO_MAX_MINUTOS).minutos == ESTOU_ATRASADO_MAX_MINUTOS


def test_estou_atrasado_rejeita_zero_ou_negativo():
    with pytest.raises(ValidationError):
        EstouAtrasadoRequest(minutos=0)
    with pytest.raises(ValidationError):
        EstouAtrasadoRequest(minutos=-5)


def test_estou_atrasado_rejeita_acima_do_teto():
    # Sem o teto, `minutos * 60` estouraria a coluna Integer (int4) do
    # `atraso_manual_segundos` — 500 em vez de 422.
    with pytest.raises(ValidationError):
        EstouAtrasadoRequest(minutos=ESTOU_ATRASADO_MAX_MINUTOS + 1)
    with pytest.raises(ValidationError):
        EstouAtrasadoRequest(minutos=40_000_000)
