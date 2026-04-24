from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, patient, public
from app.services.users import ensure_admin_user
from app.storage import build_storage_backend


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_admin_user(db)

    storage_backend = build_storage_backend()
    storage_backend.ensure_ready()
    app.state.storage_backend = storage_backend
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie="protobioptim_session",
    same_site="lax",
    https_only=settings.is_production,
    max_age=60 * 60 * 24 * 30,
)
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")

app.include_router(public.router)
app.include_router(auth.router)
app.include_router(patient.router)
app.include_router(admin.router)
