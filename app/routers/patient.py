from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import build_context, require_user, set_flash, templates
from app.models import Payment
from app.security import csrf_is_valid, ensure_csrf_token
from app.services import payments
from app.services.case_requests import (
    attach_file_to_request,
    create_case_request,
    delete_case_file,
    delete_case_request,
    get_case_file,
    get_case_request,
    list_user_requests,
    patient_can_edit_request,
    update_case_request_details,
)
from app.services.users import can_submit_requests
from app.storage import StorageError


router = APIRouter()


def _user_owns_request(case_request, current_user) -> bool:
    return bool(case_request and (case_request.user_id == current_user.id or current_user.role == "admin"))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, current_user=Depends(require_user), db: Session = Depends(get_db)):
    my_requests = list_user_requests(db, current_user)
    recent_payments = (
        db.query(Payment)
        .filter(Payment.user_id == current_user.id)
        .order_by(Payment.created_at.desc())
        .limit(5)
        .all()
    )
    answered_count = sum(1 for item in my_requests if item.interpretation)
    context = build_context(
        request,
        current_user=current_user,
        case_requests=my_requests,
        recent_payments=recent_payments,
        answered_count=answered_count,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "patient/dashboard.html", context)


@router.get("/checkout", response_class=HTMLResponse)
def checkout(request: Request, plan: str = "subscription", current_user=Depends(require_user)):
    selected_plan = payments.get_plan(plan if plan in payments.PLANS else "subscription")
    context = build_context(
        request,
        current_user=current_user,
        selected_plan_code=plan if plan in payments.PLANS else "subscription",
        selected_plan=selected_plan,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "patient/checkout.html", context)


@router.post("/checkout")
def confirm_checkout(
    request: Request,
    plan_code: str = Form(...),
    cardholder_name: str = Form(...),
    card_number: str = Form(...),
    postal_code: str = Form(...),
    consent: str = Form(...),
    csrf_token: str = Form(...),
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse("/checkout", status_code=303)
    if not consent:
        set_flash(request, "Merci de confirmer votre commande.", "error")
        return RedirectResponse(f"/checkout?plan={plan_code}", status_code=303)

    try:
        payment = payments.create_fake_payment(db, user=current_user, plan_code=plan_code)
    except ValueError as exc:
        set_flash(request, str(exc), "error")
        return RedirectResponse("/checkout", status_code=303)

    set_flash(request, f"Commande confirmee ({payment.provider_ref}).")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/requests/new", response_class=HTMLResponse)
def new_request_form(request: Request, current_user=Depends(require_user)):
    if not can_submit_requests(current_user):
        set_flash(request, "Choisissez une formule avant d'envoyer vos analyses.", "error")
        return RedirectResponse("/checkout?plan=single", status_code=303)

    context = build_context(
        request,
        current_user=current_user,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "patient/request_new.html", context)


@router.post("/requests/new")
def create_request(
    request: Request,
    age: str = Form(...),
    sex: str = Form(...),
    context_value: str = Form("", alias="context"),
    symptoms: str = Form(""),
    comment: str = Form(""),
    wants_email_copy: str | None = Form(default=None),
    csrf_token: str = Form(...),
    analysis_files: list[UploadFile] | None = File(default=None),
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse("/requests/new", status_code=303)
    if not can_submit_requests(current_user):
        set_flash(request, "Choisissez une formule avant d'envoyer vos analyses.", "error")
        return RedirectResponse("/checkout?plan=single", status_code=303)

    valid_files = [file for file in (analysis_files or []) if file.filename and file.filename.strip()]
    if not valid_files:
        set_flash(request, "Merci d'ajouter au moins un fichier d'analyse avant d'envoyer votre demande.", "error")
        return RedirectResponse("/requests/new", status_code=303)

    case_request = create_case_request(
        db,
        user=current_user,
        age=age,
        sex=sex,
        context=context_value,
        symptoms=symptoms,
        comment=comment,
        wants_email_copy=bool(wants_email_copy),
    )

    storage_backend = request.app.state.storage_backend
    uploaded_payloads = []
    try:
        for upload in valid_files:
            payload = storage_backend.upload_case_file(case_request.id, upload)
            uploaded_payloads.append(payload)
            attach_file_to_request(db, case_request=case_request, file_payload=payload)
    except StorageError as exc:
        for payload in uploaded_payloads:
            try:
                storage_backend.delete_payload(payload)
            except Exception:
                pass
        delete_case_request(db, case_request=case_request, user=current_user)
        set_flash(request, str(exc), "error")
        return RedirectResponse("/requests/new", status_code=303)

    refreshed_case_request = get_case_request(db, case_request.id)
    if not refreshed_case_request or not refreshed_case_request.files:
        delete_case_request(db, case_request=case_request, user=current_user)
        set_flash(request, "Votre demande doit contenir au moins un fichier d'analyse.", "error")
        return RedirectResponse("/requests/new", status_code=303)

    set_flash(request, "Votre demande a bien ete envoyee.")
    return RedirectResponse(f"/requests/{case_request.id}", status_code=303)


@router.get("/requests/{request_id}", response_class=HTMLResponse)
def request_detail(
    request: Request,
    request_id: int,
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    case_request = get_case_request(db, request_id)
    if not _user_owns_request(case_request, current_user):
        set_flash(request, "Ce dossier est introuvable.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    is_editable = patient_can_edit_request(case_request)
    context = build_context(
        request,
        current_user=current_user,
        case_request=case_request,
        is_editable=is_editable,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "patient/request_detail.html", context)


@router.get("/requests/{request_id}/edit", response_class=HTMLResponse)
def edit_request_form(
    request: Request,
    request_id: int,
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    case_request = get_case_request(db, request_id)
    if not _user_owns_request(case_request, current_user):
        set_flash(request, "Ce dossier est introuvable.", "error")
        return RedirectResponse("/dashboard", status_code=303)
    if not patient_can_edit_request(case_request):
        set_flash(request, "Ce dossier n'est plus modifiable car l'analyse a deja commence.", "error")
        return RedirectResponse(f"/requests/{request_id}", status_code=303)

    context = build_context(
        request,
        current_user=current_user,
        case_request=case_request,
        csrf_token=ensure_csrf_token(request.session),
    )
    return templates.TemplateResponse(request, "patient/request_edit.html", context)


@router.post("/requests/{request_id}/edit")
def edit_request(
    request: Request,
    request_id: int,
    age: str = Form(...),
    sex: str = Form(...),
    context_value: str = Form("", alias="context"),
    symptoms: str = Form(""),
    comment: str = Form(""),
    wants_email_copy: str | None = Form(default=None),
    remove_file_ids: list[int] | None = Form(default=None),
    analysis_files: list[UploadFile] | None = File(default=None),
    csrf_token: str = Form(...),
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    if not csrf_is_valid(request.session, csrf_token):
        set_flash(request, "Le formulaire a expire. Merci de recommencer.", "error")
        return RedirectResponse(f"/requests/{request_id}/edit", status_code=303)

    case_request = get_case_request(db, request_id)
    if not _user_owns_request(case_request, current_user):
        set_flash(request, "Ce dossier est introuvable.", "error")
        return RedirectResponse("/dashboard", status_code=303)
    if not patient_can_edit_request(case_request):
        set_flash(request, "Ce dossier n'est plus modifiable car l'analyse a deja commence.", "error")
        return RedirectResponse(f"/requests/{request_id}", status_code=303)

    remove_ids = {int(value) for value in (remove_file_ids or [])}
    files_to_remove = [file for file in case_request.files if file.id in remove_ids]
    valid_new_files = [file for file in (analysis_files or []) if file.filename and file.filename.strip()]
    remaining_count = len(case_request.files) - len(files_to_remove)
    final_count = remaining_count + len(valid_new_files)
    if final_count < 1:
        set_flash(request, "Votre dossier doit conserver au moins un fichier d'analyse.", "error")
        return RedirectResponse(f"/requests/{request_id}/edit", status_code=303)

    storage_backend = request.app.state.storage_backend
    uploaded_payloads = []
    try:
        for upload in valid_new_files:
            payload = storage_backend.upload_case_file(case_request.id, upload)
            uploaded_payloads.append(payload)
    except StorageError as exc:
        for payload in uploaded_payloads:
            try:
                storage_backend.delete_payload(payload)
            except Exception:
                pass
        set_flash(request, str(exc), "error")
        return RedirectResponse(f"/requests/{request_id}/edit", status_code=303)

    update_case_request_details(
        db,
        case_request=case_request,
        age=age,
        sex=sex,
        context=context_value,
        symptoms=symptoms,
        comment=comment,
        wants_email_copy=bool(wants_email_copy),
    )

    for payload in uploaded_payloads:
        attach_file_to_request(db, case_request=case_request, file_payload=payload)

    for file_record in files_to_remove:
        try:
            storage_backend.delete_case_file(file_record)
        except Exception:
            pass
        delete_case_file(db, file_record=file_record)

    set_flash(request, "Votre dossier a ete mis a jour.")
    return RedirectResponse(f"/requests/{request_id}", status_code=303)


@router.get("/files/{file_id}/preview")
def preview_file(
    request: Request,
    file_id: int,
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    file_entry = get_case_file(db, file_id)
    if not file_entry:
        set_flash(request, "Le fichier demande est introuvable.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    case_request = get_case_request(db, file_entry.case_request_id)
    if not _user_owns_request(case_request, current_user):
        set_flash(request, "Vous n'avez pas acces a ce fichier.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    storage_backend = request.app.state.storage_backend
    try:
        return storage_backend.file_response(file_entry, as_attachment=False)
    except StorageError as exc:
        set_flash(request, str(exc), "error")
        return RedirectResponse(f"/requests/{case_request.id}", status_code=303)


@router.get("/files/{file_id}")
def download_file(
    request: Request,
    file_id: int,
    current_user=Depends(require_user),
    db: Session = Depends(get_db),
):
    file_entry = get_case_file(db, file_id)
    if not file_entry:
        set_flash(request, "Le fichier demande est introuvable.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    case_request = get_case_request(db, file_entry.case_request_id)
    if not _user_owns_request(case_request, current_user):
        set_flash(request, "Vous n'avez pas acces a ce fichier.", "error")
        return RedirectResponse("/dashboard", status_code=303)

    storage_backend = request.app.state.storage_backend
    try:
        return storage_backend.file_response(file_entry, as_attachment=True)
    except StorageError as exc:
        set_flash(request, str(exc), "error")
        return RedirectResponse(f"/requests/{case_request.id}", status_code=303)
