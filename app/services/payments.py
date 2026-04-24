from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Payment, User
from app.security import new_reference, utcnow
from app.services.users import has_active_subscription


PLANS = {
    "subscription": {
        "label": "Abonnement mensuel",
        "amount_cents": 4900,
        "description": "Pour transmettre vos analyses au fil du temps et conserver un suivi dans votre espace.",
    },
    "single": {
        "label": "Analyse unique",
        "amount_cents": 6900,
        "description": "Pour une demande ponctuelle, sans engagement.",
    },
}


def get_plan(plan_code: str) -> dict:
    if plan_code not in PLANS:
        raise ValueError("Le plan selectionne est invalide.")
    return PLANS[plan_code]


def create_fake_payment(db: Session, *, user: User, plan_code: str) -> Payment:
    plan = get_plan(plan_code)
    payment = Payment(
        user_id=user.id,
        plan_code=plan_code,
        plan_label=plan["label"],
        amount_cents=plan["amount_cents"],
        status="confirmed",
        provider="fake",
        provider_ref=new_reference("BIOT"),
    )
    db.add(payment)

    now = utcnow()
    if plan_code == "subscription":
        base = user.subscription_expires_at if has_active_subscription(user) else now
        user.subscription_expires_at = base + timedelta(days=30)
    else:
        user.single_request_credits += 1

    db.commit()
    db.refresh(payment)
    db.refresh(user)
    return payment
