from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


logger = logging.getLogger(__name__)
FALLBACK_SQLITE_URL = f"sqlite:///{Path(__file__).resolve().parent.parent / 'protobioptim-fallback.db'}"


class Base(DeclarativeBase):
    pass


def _build_engine(database_url: str):
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )


_primary_engine = _build_engine(settings.database_url)
_fallback_engine = _build_engine(FALLBACK_SQLITE_URL)
_active_engine = _primary_engine
SessionLocal = sessionmaker(bind=_active_engine, autoflush=False, autocommit=False, expire_on_commit=False)

_db_ready = False
_db_lock = Lock()


def _initialize_with_engine(engine) -> None:
    Base.metadata.create_all(bind=engine)

    from app.services.users import ensure_admin_user

    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with local_session() as db:
        ensure_admin_user(db)


def ensure_database_ready() -> None:
    global _db_ready, _active_engine
    if _db_ready:
        return

    with _db_lock:
        if _db_ready:
            return

        try:
            _initialize_with_engine(_primary_engine)
            _active_engine = _primary_engine
            SessionLocal.configure(bind=_primary_engine)
        except Exception:
            logger.exception("Primary database initialization failed; falling back to local SQLite.")
            _initialize_with_engine(_fallback_engine)
            _active_engine = _fallback_engine
            SessionLocal.configure(bind=_fallback_engine)

        _db_ready = True


def get_db() -> Generator[Session, None, None]:
    ensure_database_ready()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
