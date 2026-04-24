from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import build_context, require_admin, set_flash, templates
from app.security import csrf_is_valid, ensure_csrf_token
from app.services.case_requests import get_case_request, list_recent_requests, update_case_request


router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, current_user=Depends(require_admin), db: Session = Depends(get_db)):
    requests_list = list_recent_requests(db)
    context = build_context(
        request,
        current_user=current_user,
        requests_list=requests_list,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "admin/dashboard.html", context)


@router.get("/admin/requests/{request_id}", response_class=HTMLResponse)
def admin_request_detail(
    request: Request,
    request_id: int,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    case_request = get_case_request(db, request_id)
    if not case_request:
        set_flash(request, "Ce dossier est introuvable.", "error")
        return RedirectResponse("/admin", status_code=303)

    context = build_context(
        request,
        current_user=current_user,
        case_request=case_request,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "admin/request_detail.html", context)


@router.post("/admin/requests/{request_id}")
def admin_update_request(
    request: Request,
    request_id: int,
    status: str = Form(...),
    interpretation: str = Form(""),
    csrf_token: str = Form(...),
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse(f"/admin/requests/{request_id}", status_code=303)

    case_request = get_case_request(db, request_id)
    if not case_request:
        set_flash(request, "Ce dossier est introuvable.", "error")
        return RedirectResponse("/admin", status_code=303)

    if status in {"answered", "closed"} and not interpretation.strip():
        set_flash(request, "Une reponse ecrite est requise pour finaliser le dossier.", "error")
        return RedirectResponse(f"/admin/requests/{request_id}", status_code=303)

    update_case_request(
        db,
        case_request=case_request,
        status=status,
        interpretation=interpretation.strip(),
    )
    set_flash(request, "Le dossier a ete mis a jour.")
    return RedirectResponse(f"/admin/requests/{request_id}", status_code=303)
