import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("admins.id", ondelete="CASCADE"), index=True, nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Enquiry(Base):
    __tablename__ = "enquiries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_enquiries_idempotency_key"),
        Index("ix_enquiries_created_status", "submitted_at", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(64))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    parent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    preferred_contact_method: Mapped[str] = mapped_column(String(20), nullable=False)
    students_in_home: Mapped[int] = mapped_column(Integer, nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    locality: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    pin_code: Mapped[str] = mapped_column(String(6), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    tutor_gender_preference: Mapped[str | None] = mapped_column(String(40))
    preferred_qualification: Mapped[str | None] = mapped_column(String(120))
    teaching_language: Mapped[str | None] = mapped_column(String(80))
    preferred_time: Mapped[str | None] = mapped_column(String(40))
    classes_per_week: Mapped[str | None] = mapped_column(String(30))
    session_duration: Mapped[str | None] = mapped_column(String(40))
    additional_requirements: Mapped[str | None] = mapped_column(String(1000))
    consent: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    privacy_notice_version: Mapped[str] = mapped_column(String(40), nullable=False)
    individual_fee_subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    combined_monthly_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fee_status: Mapped[str] = mapped_column(String(30), default="unavailable", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="New", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    students: Mapped[list["Student"]] = relationship(
        back_populates="enquiry", cascade="all, delete-orphan", order_by="Student.student_number"
    )
    notes: Mapped[list["EnquiryNote"]] = relationship(
        back_populates="enquiry", cascade="all, delete-orphan", order_by="EnquiryNote.created_at"
    )


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("enquiry_id", "student_number", name="uq_student_number_per_enquiry"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enquiries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_number: Mapped[int] = mapped_column(Integer, nullable=False)
    student_name: Mapped[str | None] = mapped_column(String(120))
    class_or_grade: Mapped[str] = mapped_column(String(80), nullable=False)
    board: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_stream: Mapped[str | None] = mapped_column(String(80))
    subjects: Mapped[str | None] = mapped_column(String(300))
    tuition_type: Mapped[str | None] = mapped_column(String(40))
    individual_monthly_fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    fee_status: Mapped[str] = mapped_column(String(30), default="unavailable", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    enquiry: Mapped[Enquiry] = relationship(back_populates="students")


class EnquiryNote(Base):
    __tablename__ = "enquiry_notes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    enquiry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("enquiries.id", ondelete="CASCADE"), index=True, nullable=False
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False
    )
    note: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    enquiry: Mapped[Enquiry] = relationship(back_populates="notes")
