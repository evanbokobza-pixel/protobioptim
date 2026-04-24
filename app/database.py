from __future__ import annotations

from collections.abc import Generator
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

_db_ready = False
_db_lock = Lock()


def ensure_database_ready() -> None:
    global _db_ready
    if _db_ready:
        return

    with _db_lock:
        if _db_ready:
            return

        Base.metadata.create_all(bind=engine)

        from app.services.users import ensure_admin_user

        with SessionLocal() as db:
            ensure_admin_user(db)

        _db_ready = True


def get_db() -> Generator[Session, None, None]:
    ensure_database_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
