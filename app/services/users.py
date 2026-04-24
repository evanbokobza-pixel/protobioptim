from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password, password_is_valid, utcnow, verify_password


def get_user_by_id(db: Session, user_id: int | None) -> User | None:
    if not user_id:
        return None
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def ensure_admin_user(db: Session) -> None:
    existing = get_user_by_email(db, settings.admin_email)
    if existing:
        return

    admin = User(
        full_name="Protobioptim Admin",
        email=settings.admin_email,
        password_hash=hash_password(settings.admin_password),
        role="admin",
        subscription_expires_at=utcnow() + timedelta(days=3650),
        single_request_credits=999,
    )
    db.add(admin)
    db.commit()


def create_user(db: Session, *, full_name: str, email: str, password: str) -> User:
    if get_user_by_email(db, email):
        raise ValueError("Un compte existe deja avec cette adresse email.")
    if not password_is_valid(password):
        raise ValueError("Choisissez un mot de passe d'au moins 8 caracteres avec 1 chiffre.")

    user = User(
        full_name=full_name.strip(),
        email=email.strip().lower(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def has_active_subscription(user: User) -> bool:
    return bool(user.subscription_expires_at and user.subscription_expires_at > utcnow())


def access_label(user: User | None) -> str:
    if not user:
        return "Aucune formule active"
    if user.role == "admin":
        return "Acces administrateur"
    if has_active_subscription(user):
        date_label = user.subscription_expires_at.astimezone().strftime("%d/%m/%Y")
        return f"Abonnement actif jusqu'au {date_label}"
    if user.single_request_credits > 0:
        if user.single_request_credits == 1:
            return "1 demande ponctuelle disponible"
        return f"{user.single_request_credits} demandes ponctuelles disponibles"
    return "Aucune formule active"


def can_submit_requests(user: User | None) -> bool:
    return bool(user and (user.role == "admin" or has_active_subscription(user) or user.single_request_credits > 0))
