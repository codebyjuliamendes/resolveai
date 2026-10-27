"""Configuração via variáveis de ambiente (e `.env`, quando presente)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _default_static_dir() -> Path:
    # Em desenvolvimento (layout src/) o frontend fica na raiz do repositório;
    # na imagem Docker o caminho é definido por STATIC_DIR.
    candidate = _PROJECT_ROOT / "public"
    return candidate if candidate.is_dir() else Path.cwd() / "public"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production", "test"] = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=3004, ge=1, le=65535)

    database_url: str = ""
    # Compatibilidade com a versão Node, que aceitava DATABASE_PATH.
    database_path: Path | None = None
    auto_migrate: bool = True
    seed_demo_data: bool = True

    static_dir: Path = Field(default_factory=_default_static_dir)
    docs_enabled: bool = True

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    max_body_bytes: int = Field(default=48 * 1024, ge=1024)
    rate_limit_enabled: bool = True
    rate_limit_writes_per_minute: int = Field(default=60, ge=1)
    rate_limit_suggest_per_minute: int = Field(default=12, ge=1)
    hsts_enabled: bool = False

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    openai_max_output_tokens: int = Field(default=400, ge=50, le=4000)

    @model_validator(mode="after")
    def _resolve_database_url(self) -> Settings:
        if not self.database_url:
            path = self.database_path or Path("data") / "support.sqlite"
            self.database_url = f"sqlite:///{path}"
        # Variáveis vazias no .env equivalem a "não configurado".
        if self.openai_api_key is not None and not self.openai_api_key.get_secret_value().strip():
            self.openai_api_key = None
        if self.openai_model is not None and not self.openai_model.strip():
            self.openai_model = None
        return self

    @property
    def openai_enabled(self) -> bool:
        return self.openai_api_key is not None and self.openai_model is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
