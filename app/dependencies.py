from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.security import ensure_csrf_token
from app.services import payments
from app.services.users import access_label, get_user_by_id


templates = Jinja2Templates(directory=str(settings.templates_dir))


STATUS_LABELS = {
    "submitted": "Dossier recu",
    "reviewing": "Analyse en cours",
    "answered": "Compte rendu disponible",
    "closed": "Dossier cloture",
}

PAYMENT_STATUS_LABELS = {
    "confirmed": "Confirme",
    "pending": "En attente",
    "failed": "Echoue",
}


def format_money(cents: int) -> str:
    euros = cents / 100
    if euros.is_integer():
        return f"{int(euros)} EUR"
    return f"{euros:.2f} EUR"


def format_datetime(value) -> str:
    if not value:
        return "-"
    return value.astimezone().strftime("%d/%m/%Y a %H:%M")


templates.env.filters["money"] = format_money
templates.env.filters["datetime"] = format_datetime
templates.env.globals["status_label"] = lambda status_code: STATUS_LABELS.get(status_code, status_code)
templates.env.globals["payment_status_label"] = lambda status_code: PAYMENT_STATUS_LABELS.get(status_code, status_code)
templates.env.globals["plans"] = payments.PLANS


def set_flash(request: Request, message: str, kind: str = "success") -> None:
    request.session["flash"] = {"message": message, "kind": kind}


def pop_flash(request: Request) -> dict[str, str] | None:
    return request.session.pop("flash", None)


def build_context(request: Request, *, current_user=None, **extra: Any) -> dict[str, Any]:
    return {
        "request": request,
        "app_name": settings.app_name,
        "current_user": current_user,
        "access_label": access_label(current_user),
        "flash": pop_flash(request),
        "csrf_token": ensure_csrf_token(request.session),
        **extra,
    }


def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    return get_user_by_id(db, user_id)


def require_user(current_user=Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return current_user


def require_admin(current_user=Depends(require_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acces refuse")
    return current_user
