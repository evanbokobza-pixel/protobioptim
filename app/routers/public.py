from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import build_context, get_current_user, templates


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def home(request: Request, current_user=Depends(get_current_user)):
    context = build_context(request, current_user=current_user)
    return templates.TemplateResponse(request, "home.html", context)


@router.get("/health")
def health():
    return {"status": "ok"}
