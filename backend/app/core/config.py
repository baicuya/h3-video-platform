from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_secret_key: str = "development-only-change-me"
    public_origin: str = "http://127.0.0.1"
    database_url: str = "postgresql+asyncpg://h3_platform@127.0.0.1/h3_video_platform"
    redis_url: str = "redis://127.0.0.1:6379/0"
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_ws_url: str = "ws://127.0.0.1:8188/ws"
    storage_root: Path = Path("/home/ubuntu/data")
    workflow_root: Path = PROJECT_ROOT.parent / "workflows"
    cookie_name: str = "h3_session"
    cookie_secure: bool = False
    cookie_max_age_seconds: int = 12 * 60 * 60
    login_max_failures: int = 5
    login_lock_seconds: int = 15 * 60
    gpu_max_concurrency: int = 1
    max_image_mb: int = 20
    max_video_mb: int = 500
    max_audio_mb: int = 100
    ref2va_enabled: bool = False
    trusted_hosts: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache
def get_settings() -> Settings:
    return Settings()

