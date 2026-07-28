"""Configuração central da aplicação (lida do .env via pydantic-settings)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de placeholder do `.env.example`. Fora de `development`, subir com ele
# (ou com qualquer segredo curto) é bloqueado no boot — TODO o isolamento
# multi-tenant tem raiz na integridade do JWT (`app/api/deps.py::get_tenant_db`
# seta `app.tenant_id` a partir da claim; `require_role` lê o papel da claim).
# Um segredo forjável colapsa RLS+RBAC de uma vez. Ver revisão de segurança,
# achado A1.
_DEFAULT_JWT_SECRET = "troque-este-valor"
_JWT_SECRET_MIN_LEN = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Banco
    database_url: str = "postgresql+psycopg://user:pass@localhost:5432/vaivem"

    # Supabase (opcional — Data API / chaves)
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = "troque-este-valor"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Integrações externas
    google_maps_api_key: str | None = None
    fcm_server_key: str | None = None
    payment_gateway_token: str | None = None

    # App
    env: str = "development"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"

    @model_validator(mode="after")
    def _exigir_jwt_secret_forte_fora_de_dev(self) -> "Settings":
        """Fail-closed no boot (achado A1). Em `development` o default é
        tolerado (DX local); em qualquer outro ambiente, um segredo default ou
        curto é erro de configuração fatal — melhor não subir do que subir
        forjável."""
        if not self.is_development and (
            self.jwt_secret == _DEFAULT_JWT_SECRET or len(self.jwt_secret) < _JWT_SECRET_MIN_LEN
        ):
            raise ValueError(
                f"JWT_SECRET inseguro para env='{self.env}': defina um segredo forte "
                f"(>= {_JWT_SECRET_MIN_LEN} caracteres e diferente do placeholder). "
                "Sem isso, qualquer um pode forjar tokens e furar RLS/RBAC."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Settings em cache — evita reler o .env a cada chamada."""
    return Settings()
