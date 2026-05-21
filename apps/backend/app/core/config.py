from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # =========================================================
    # Core App
    # =========================================================

    app_name: str = "LogIQ Platform"

    environment: Literal[
        "development",
        "staging",
        "production",
        "test",
    ] = "development"

    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    # =========================================================
    # Database
    # =========================================================

    database_url: str = (
        "postgresql+asyncpg://logiq@localhost:5432/logiq"
    )

    sync_database_url: str = (
        "postgresql://logiq@localhost:5432/logiq"
    )

    redis_url: str | None = None

    # =========================================================
    # Kafka
    # =========================================================

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_enabled: bool = False

    # =========================================================
    # Observability
    # =========================================================

    otel_exporter_otlp_endpoint: str | None = None

    # =========================================================
    # CORS
    # =========================================================

    backend_cors_origins: list[str] | str = Field(
        default_factory=lambda: [
            "http://localhost:3000"
        ]
    )

    # =========================================================
    # Authentication / Security
    # =========================================================

    jwt_secret: SecretStr | None = None
    jwt_secret_file: str | None = None
    # Secondary secret for zero-downtime JWT key rotation.
    # Tokens signed with the old key can still be verified during the
    # rotation window.  Remove once all tokens have naturally expired.
    jwt_secret_secondary: SecretStr | None = None

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14

    refresh_cookie_name: str = "logiq_refresh"

    bcrypt_rounds: int = 12

    # =========================================================
    # Rate Limiting
    # =========================================================

    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60

    login_rate_limit_requests: int = 10
    login_account_rate_limit_requests: int = 8

    auth_rate_limit_requests: int = 10

    login_fail_alert_threshold: int = 5

    # Account lockout (brute-force protection)
    account_lockout_max_attempts: int = 10
    account_lockout_duration_seconds: int = 900  # 15 minutes

    # =========================================================
    # Request Security
    # =========================================================

    max_request_body_size_bytes: int = 10 * 1024 * 1024  # 10 MB default

    # =========================================================
    # Registration
    # =========================================================

    public_registration_enabled: bool | None = None

    # =========================================================
    # AI / Embeddings
    # =========================================================

    embedding_provider: Literal[
        "hash",
        "openai",
        "anthropic",
        "lexical_hash_dev",
    ] = "hash"

    embedding_api_url: str | None = None

    embedding_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    voyageai_api_key: SecretStr | None = None

    sentence_transformer_model: str = "all-MiniLM-L6-v2"
    triage_mode: Literal["heuristic", "claude_pipeline"] = "heuristic"
    llm_cost_tracking_enabled: bool = True

    embedding_model: str = "provider-default"

    embedding_dimensions: int = 384

    planner_model: Literal[
        "claude-sonnet-4-20250514",
        "claude-opus-4",
        "gpt-4.1",
    ] = "claude-sonnet-4-20250514"

    # =========================================================
    # AI Retry / Execution Limits
    # =========================================================

    max_triage_retries: int = 2
    max_tool_retries: int = 3

    llm_timeout_seconds: int = 60
    tool_timeout_seconds: int = 20

    max_consecutive_llm_failures: int = 5

    llm_requests_per_minute: int = 60

    max_daily_llm_cost_usd: float = 50.0

    # =========================================================
    # Chunking / Retrieval
    # =========================================================

    chunk_size_tokens: int = 200
    chunk_overlap_tokens: int = 50

    log_triage_limit: int = 1000

    # =========================================================
    # Evaluation
    # =========================================================

    eval_f1_pass_threshold: float = 0.80

    # =========================================================
    # Validators
    # =========================================================

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: Any) -> list[str]:
        """
        Allows:
        BACKEND_CORS_ORIGINS=http://a.com,http://b.com
        """
        if isinstance(value, str):
            return [
                origin.strip()
                for origin in value.split(",")
                if origin.strip()
            ]
        return value

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> "Settings":
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError(
                "chunk_overlap_tokens must be smaller than chunk_size_tokens"
            )

        return self

    @model_validator(mode="after")
    def validate_database_urls(self) -> "Settings":
        if self.is_production:
            if "localhost" in self.database_url:
                raise ValueError(
                    "Production database_url cannot use localhost"
                )

            if "localhost" in self.sync_database_url:
                raise ValueError(
                    "Production sync_database_url cannot use localhost"
                )

        return self

    @model_validator(mode="after")
    def validate_embedding_provider(self) -> "Settings":
        provider = self.embedding_provider.lower()

        if provider == "anthropic":
            if not self.anthropic_api_key:
                raise ValueError(
                    "anthropic_api_key is required when using anthropic embeddings"
                )

        if provider == "openai":
            if not self.openai_api_key:
                raise ValueError(
                    "openai_api_key is required when using openai embeddings"
                )

        if provider == "voyageai":
            if not self.voyageai_api_key:
                raise ValueError(
                    "voyageai_api_key is required when using voyageai embeddings"
                )

        if self.is_production and provider in ["lexical_hash_dev", "hash"]:
            raise ValueError(
                "Production requires a semantic embedding provider"
            )

        return self

    # =========================================================
    # Computed Properties
    # =========================================================

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def effective_jwt_secret(self) -> str:
        """
        Resolve JWT secret from:
        1. JWT_SECRET_FILE
        2. JWT_SECRET
        """

        if self.jwt_secret_file:
            secret = (
                Path(self.jwt_secret_file)
                .read_text(encoding="utf-8")
                .strip()
            )

            if len(secret) >= 32:
                return secret

        if self.jwt_secret:
            raw_secret = self.jwt_secret.get_secret_value()

            if len(raw_secret) >= 32:
                return raw_secret

        if self.is_production:
            raise RuntimeError(
                "JWT_SECRET must contain at least 32 characters in production"
            )

        raise RuntimeError(
            "JWT_SECRET or JWT_SECRET_FILE is required"
        )

    @property
    def effective_jwt_secrets(self) -> list[str]:
        """Return [primary, secondary] secrets for rotation-aware decode.

        The first entry is always used for signing new tokens.
        Secondary is used only for verifying tokens signed with the old key
        during a rolling rotation window.
        """
        secrets_list = [self.effective_jwt_secret]
        if self.jwt_secret_secondary:
            raw = self.jwt_secret_secondary.get_secret_value()
            if len(raw) >= 32:
                secrets_list.append(raw)
        return secrets_list

    @property
    def allow_public_registration(self) -> bool:
        """
        Public registration defaults:
        - enabled in development
        - disabled in production
        """

        if self.public_registration_enabled is not None:
            return self.public_registration_enabled

        return not self.is_production

    @property
    def effective_embedding_provider(self) -> str:
        return self.embedding_provider.lower()


# =============================================================
# Cached Singleton Settings
# =============================================================

@lru_cache
def get_settings() -> Settings:
    return Settings()