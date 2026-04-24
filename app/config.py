from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://") and "+psycopg" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_name: str
    public_app_url: str
    session_secret_key: str
    database_url: str
    supabase_url: str
    supabase_service_role_key: str
    supabase_storage_bucket: str
    storage_backend: str
    admin_email: str
    admin_password: str
    max_upload_size_mb: int
    signed_url_ttl_seconds: int
    uploads_dir: Path
    templates_dir: Path
    static_dir: Path

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def uses_supabase_storage(self) -> bool:
        return (
            self.storage_backend == "supabase"
            and bool(self.supabase_url)
            and bool(self.supabase_service_role_key)
        )


def get_settings() -> Settings:
    database_url = _normalize_database_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'protobioptim.db'}")
    )
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        app_name=os.getenv("APP_NAME", "Bioptim"),
        public_app_url=os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:8000"),
        session_secret_key=os.getenv("SESSION_SECRET_KEY", "change-me-in-production"),
        database_url=database_url,
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip(),
        supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "bioptim-files").strip(),
        storage_backend=os.getenv("STORAGE_BACKEND", "supabase").strip().lower(),
        admin_email=os.getenv("ADMIN_EMAIL", "admin@bioptim.local").strip().lower(),
        admin_password=os.getenv("ADMIN_PASSWORD", "ChangeMe123!"),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "8")),
        signed_url_ttl_seconds=int(os.getenv("SIGNED_URL_TTL_SECONDS", "900")),
        uploads_dir=BASE_DIR / "uploads",
        templates_dir=BASE_DIR / "app" / "templates",
        static_dir=BASE_DIR / "app" / "static",
    )


settings = get_settings()
