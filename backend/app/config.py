"""Application settings, loaded from backend/.env (falls back to sane defaults)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # repo root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend" / ".env", extra="ignore"
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/dse_market"
    )
    cors_origins: str = "http://localhost:5173"
    reports_dir: Path = ROOT / "reports"
    frontend_dist: Path = ROOT / "frontend" / "dist"
    seed_csv: Path = ROOT / "data" / "portfolio.csv"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
