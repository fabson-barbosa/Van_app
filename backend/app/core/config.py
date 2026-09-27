"""Configuração central da aplicação (lida do .env via pydantic-settings)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Valor de exemplo do `.env.example`. Serve para `ENV=development` e é
#: explicitamente recusado em qualquer outro ambiente (ver validador abaixo).
JWT_SECRET_PADRAO = "troque-este-valor"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Banco
    database_url: str = "postgresql+psycopg://user:pass@localhost:5432/vaivem"

    # Pool por PROCESSO. No Cloud Run cada instância tem o seu, então o total de
    # conexões é (db_pool_size + db_max_overflow) × max-instances — e o menor
    # tier do Cloud SQL aceita 25. Ver comentário em `app/core/db.py`.
    db_pool_size: int = 2
    db_max_overflow: int = 1

    # Supabase (opcional — Data API / chaves)
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_secret_key: str | None = None

    # Redis — declarado desde o Sprint 0 e AINDA NÃO USADO por nenhum módulo
    # (nenhum import de `redis` em `app/` ou `scripts/`). Fica aqui porque o
    # `.env.example` o documenta, mas o deploy NÃO precisa provisionar
    # Memorystore: ver `deploy/README.md`.
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret: str = JWT_SECRET_PADRAO
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
    def _exigir_segredos_fora_de_desenvolvimento(self) -> "Settings":
        """Recusa subir em produção com segredo de exemplo.

        É a pior configuração incorreta possível neste app e a mais silenciosa:
        o `jwt_secret` assina os tokens que carregam `tenant_id` e `role`. Com o
        valor padrão — que está no `.env.example`, versionado e público — QUALQUER
        pessoa forja um token de admin de QUALQUER tenant, e o RLS não protege
        nada, porque a sessão passa a setar o `app.tenant_id` que o atacante
        escolheu (CLAUDE.md §7.3 confia na identidade do token).

        Sem esta guarda, um deploy que esquecesse de montar o segredo do Secret
        Manager subiria saudável, responderia 200 no `/health` e passaria todo
        teste de fumaça. Falhar no start é a única forma de isso não passar.
        """
        if self.is_development:
            return self
        if self.jwt_secret == JWT_SECRET_PADRAO or len(self.jwt_secret) < 32:
            raise ValueError(
                "JWT_SECRET ausente, igual ao valor de exemplo, ou curto demais "
                f"(< 32 caracteres) com ENV={self.env!r}. Gere um segredo real e "
                "monte-o via Secret Manager — ver deploy/README.md."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """Settings em cache — evita reler o .env a cada chamada."""
    return Settings()
