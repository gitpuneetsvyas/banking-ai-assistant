from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings. Environment variables use the BANK_ prefix."""

    model_config = SettingsConfigDict(env_prefix="BANK_", extra="ignore")

    data_dir: Path = BACKEND_ROOT / "data"
    jwt_secret: str = "poc-only-not-for-production"
    jwt_ttl_minutes: int = 480
    llm_provider: str = "deterministic"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "qwen2.5:3b"
    llm_api_key: str = "ollama"
    llm_timeout_seconds: float = 20
    accounts_enabled: bool = True
    rate_limit_per_minute: int = 60
    login_limit_per_minute: int = 20
    bank_name: str = "Harbourline Bank"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    @property
    def knowledge_dir(self) -> Path:
        return BACKEND_ROOT / "knowledge"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bank.db"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def pdf_dir(self) -> Path:
        return self.data_dir / "pdfs"
