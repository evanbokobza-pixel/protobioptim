from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import build_context, set_flash, templates
from app.security import csrf_is_valid, ensure_csrf_token
from app.services.users import authenticate_user, create_user


router = APIRouter()


@router.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    context = build_context(request, csrf_token=ensure_csrf_token(request.session))
    return templates.TemplateResponse(request, "auth/signup.html", context)


@router.post("/signup")
def signup(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse("/signup", status_code=303)
    if password != password_confirm:
        set_flash(request, "Les mots de passe ne correspondent pas.", "error")
        return RedirectResponse("/signup", status_code=303)

    try:
        user = create_user(db, full_name=full_name, email=email, password=password)
    except ValueError as exc:
        set_flash(request, str(exc), "error")
        return RedirectResponse("/signup", status_code=303)

    request.session["user_id"] = user.id
    set_flash(request, "Votre compte a bien ete cree.")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    context = build_context(request, csrf_token=ensure_csrf_token(request.session))
    return templates.TemplateResponse(request, "auth/login.html", context)


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse("/login", status_code=303)

    user = authenticate_user(db, email=email, password=password)
    if not user:
        set_flash(request, "Email ou mot de passe incorrect.", "error")
        return RedirectResponse("/login", status_code=303)

    request.session["user_id"] = user.id
    set_flash(request, "Connexion reussie.")
    target = "/admin" if user.role == "admin" else "/dashboard"
    return RedirectResponse(target, status_code=303)


@router.post("/logout")
def logout(request: Request, csrf_token: str = Form(...)):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse("/", status_code=303)

    request.session.clear()
    set_flash(request, "Vous etes maintenant deconnecte.")
    return RedirectResponse("/", status_code=303)
