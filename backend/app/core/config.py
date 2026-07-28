"""Configuração central da aplicação (lida do .env via pydantic-settings)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # WhatsApp via Twilio Sandbox (piloto — ver PROGRESSO.md sobre limitações)
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str | None = None  # E.164 do número do sandbox, sem prefixo "whatsapp:"

    # App
    env: str = "development"

    @property
    def is_development(self) -> bool:
        return self.env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    """Settings em cache — evita reler o .env a cada chamada."""
    return Settings()
