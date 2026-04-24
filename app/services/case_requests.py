from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models import CaseFile, CaseRequest, User
from app.services.users import has_active_subscription


def list_user_requests(db: Session, user: User) -> list[CaseRequest]:
    return (
        db.query(CaseRequest)
        .options(joinedload(CaseRequest.files))
        .filter(CaseRequest.user_id == user.id)
        .order_by(CaseRequest.created_at.desc())
        .all()
    )


def list_recent_requests(db: Session, limit: int = 12) -> list[CaseRequest]:
    return (
        db.query(CaseRequest)
        .options(joinedload(CaseRequest.user), joinedload(CaseRequest.files))
        .order_by(CaseRequest.created_at.desc())
        .limit(limit)
        .all()
    )


def get_case_request(db: Session, request_id: int) -> CaseRequest | None:
    return (
        db.query(CaseRequest)
        .options(joinedload(CaseRequest.files), joinedload(CaseRequest.user))
        .filter(CaseRequest.id == request_id)
        .first()
    )


def create_case_request(
    db: Session,
    *,
    user: User,
    age: str,
    sex: str,
    context: str,
    symptoms: str,
    comment: str,
    wants_email_copy: bool,
) -> CaseRequest:
    case_request = CaseRequest(
        user_id=user.id,
        request_type="Abonnement" if has_active_subscription(user) else "Analyse unique",
        status="submitted",
        age=age,
        sex=sex,
        context=context or None,
        symptoms=symptoms or None,
        comment=comment or None,
        wants_email_copy=wants_email_copy,
    )
    db.add(case_request)

    if user.role != "admin" and not has_active_subscription(user):
        user.single_request_credits -= 1

    db.commit()
    db.refresh(case_request)
    return case_request


def attach_file_to_request(db: Session, *, case_request: CaseRequest, file_payload) -> CaseFile:
    case_file = CaseFile(
        case_request_id=case_request.id,
        original_name=file_payload.original_name,
        storage_provider=file_payload.provider,
        storage_bucket=file_payload.bucket,
        storage_path=file_payload.path,
        mime_type=file_payload.mime_type,
        size_bytes=file_payload.size_bytes,
    )
    db.add(case_file)
    db.commit()
    db.refresh(case_file)
    return case_file


def update_case_request(
    db: Session,
    *,
    case_request: CaseRequest,
    status: str,
    interpretation: str,
) -> CaseRequest:
    case_request.status = status
    case_request.interpretation = interpretation or None
    db.commit()
    db.refresh(case_request)
    return case_request
