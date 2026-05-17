from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_name: str = "LogIQ Platform"
    environment: str = Field(default="development")
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://logiq@localhost:5432/logiq"
    sync_database_url: str = "postgresql://logiq@localhost:5432/logiq"
    redis_url: str | None = None
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_enabled: bool = True
    otel_exporter_otlp_endpoint: str | None = None
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    jwt_secret: str | None = None
    jwt_secret_file: str | None = None
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    refresh_cookie_name: str = "logiq_refresh"
    bcrypt_rounds: int = 12
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    login_rate_limit_requests: int = 10
    login_account_rate_limit_requests: int = 8
    auth_rate_limit_requests: int = 10  # Combined login+register limit per IP per window
    login_fail_alert_threshold: int = 5  # Log ERROR after this many consecutive failures per email
    public_registration_enabled: bool | None = None
    embedding_provider: str = "lexical_hash_dev"
    embedding_api_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model: str = "provider-default"
    embedding_dimensions: int = 384

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def effective_jwt_secret(self) -> str:
        if self.jwt_secret_file:
            secret = Path(self.jwt_secret_file).read_text(encoding="utf-8").strip()
            if len(secret) >= 32:
                return secret
        if self.jwt_secret and len(self.jwt_secret) >= 32:
            return self.jwt_secret
        if self.is_production:
            raise RuntimeError("JWT_SECRET must be provided with at least 32 characters in production")
        raise RuntimeError("JWT_SECRET or JWT_SECRET_FILE is required")

    @property
    def allow_public_registration(self) -> bool:
        if self.public_registration_enabled is not None:
            return self.public_registration_enabled
        return not self.is_production

    @property
    def effective_embedding_provider(self) -> str:
        provider = self.embedding_provider.lower()
        if self.is_production and provider == "lexical_hash_dev":
            raise RuntimeError("Production requires a semantic embedding provider")
        return provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
