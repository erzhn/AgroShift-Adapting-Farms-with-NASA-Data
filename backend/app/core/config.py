"""Настройки приложения. Все секреты — только из переменных окружения (раздел 12.3)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    app_name: str = "AgroShift API"
    environment: str = "dev"
    database_url: str = "postgresql+psycopg://agroshift:agroshift@localhost:5433/agroshift"

    # Демо-режим хакатона (раздел 14.1): без SMS-входа, роль из заголовка X-Demo-Role
    demo_mode: bool = True
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 30  # раздел 12.3: срок сессии 30 дней

    cors_origins: list[str] = ["http://localhost:3000"]

    # Все даты — в Asia/Bishkek (инвариант 7.2)
    timezone: str = "Asia/Bishkek"

    # Хранилище снимков данных (на хакатоне — локальная папка, далее MinIO/S3)
    snapshots_dir: Path = BACKEND_DIR / "data" / "snapshots"
    runs_dir: Path = BACKEND_DIR / "data" / "runs"

    # ИИ-помощник (раздел 10)
    llm_provider: str = "none"
    llm_model: str = ""
    llm_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
