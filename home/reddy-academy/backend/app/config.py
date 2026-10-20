from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_DIR / "frontend"


class Settings(BaseSettings):
    database_url: str | None = None
    secret_key: str | None = None
    environment: str = "development"
    session_cookie_secure: bool = False
    session_ttl_hours: int = Field(default=8, ge=1, le=168)
    frontend_origin: str = "http://localhost:5500"
    privacy_notice_version: str = "2026-01"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_database_url(self) -> str:
        if not self.database_url:
            raise RuntimeError(
                "DATABASE_URL is missing. Copy backend/.env.example to backend/.env "
                "and configure the Supabase PostgreSQL connection."
            )
        return self.database_url.replace("postgres://", "postgresql+psycopg://", 1).replace(
            "postgresql://", "postgresql+psycopg://", 1
        )

    def get_secret_key(self) -> str:
        if not self.secret_key or len(self.secret_key) < 32:
            raise RuntimeError(
                "SECRET_KEY must be configured in backend/.env with at least 32 characters."
            )
        return self.secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
