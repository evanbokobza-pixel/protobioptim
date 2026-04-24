from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="patient", index=True)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    single_request_credits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    payments: Mapped[list["Payment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    case_requests: Mapped[list["CaseRequest"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(40))
    plan_label: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="confirmed")
    provider: Mapped[str] = mapped_column(String(40), default="fake")
    provider_ref: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="payments")


class CaseRequest(Base):
    __tablename__ = "case_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    age: Mapped[str] = mapped_column(String(50))
    sex: Mapped[str] = mapped_column(String(50))
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    symptoms: Mapped[str | None] = mapped_column(Text, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    wants_email_copy: Mapped[bool] = mapped_column(Boolean, default=False)
    interpretation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="case_requests")
    files: Mapped[list["CaseFile"]] = relationship(back_populates="case_request", cascade="all, delete-orphan")


class CaseFile(Base):
    __tablename__ = "case_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_request_id: Mapped[int] = mapped_column(ForeignKey("case_requests.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_provider: Mapped[str] = mapped_column(String(40), default="local")
    storage_bucket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    case_request: Mapped[CaseRequest] = relationship(back_populates="files")
