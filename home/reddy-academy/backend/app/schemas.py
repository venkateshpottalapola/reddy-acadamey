from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


Status = Literal["New", "Contacted", "Follow-up Required", "Converted", "Closed"]


class StudentCreate(BaseModel):
    student_name: str | None = Field(default=None, max_length=120)
    grade: str = Field(min_length=1, max_length=80)
    board: str = Field(min_length=1, max_length=100)
    custom_board: str | None = Field(default=None, max_length=100)
    stream: str | None = Field(default=None, max_length=80)
    subjects: str | None = Field(default=None, max_length=300)
    tuition_type: str | None = Field(default=None, max_length=40)

    @field_validator("grade")
    @classmethod
    def validate_grade(cls, value: str) -> str:
        supported = {
            "Nursery", "LKG", "UKG",
            *(f"Class {number}" for number in range(1, 13)),
            "Intermediate 1st Year", "Intermediate 2nd Year",
            "Other or equivalent academic level",
        }
        if value not in supported:
            raise ValueError("Select a supported class or academic level")
        return value

    @field_validator("board")
    @classmethod
    def validate_board(cls, value: str) -> str:
        if value not in {"CBSE", "ICSE", "State Board", "IB", "IGCSE", "other"}:
            raise ValueError("Select a supported education board")
        return value

    @model_validator(mode="after")
    def custom_board_required(self):
        if self.board == "other" and not (self.custom_board and self.custom_board.strip()):
            raise ValueError("custom_board is required when board is Other")
        return self


class EnquiryCreate(BaseModel):
    idempotency_key: str = Field(min_length=16, max_length=64)
    parent_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=32)
    email: EmailStr | None = None
    preferred_contact_method: Literal["Phone", "WhatsApp", "Email"]
    students: list[StudentCreate] = Field(min_length=1, max_length=10)
    tutor_gender: str | None = Field(default=None, max_length=40)
    qualification: str | None = Field(default=None, max_length=120)
    language: str | None = Field(default=None, max_length=80)
    preferred_time: str | None = Field(default=None, max_length=40)
    classes_per_week: str | None = Field(default=None, max_length=30)
    session_duration: str | None = Field(default=None, max_length=40)
    city: str = Field(min_length=1, max_length=100)
    locality: str = Field(min_length=1, max_length=120)
    pin_code: str = Field(pattern=r"^\d{6}$")
    address: str | None = Field(default=None, max_length=500)
    message: str | None = Field(default=None, max_length=1000)
    consent: bool

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        digits = "".join(character for character in value if character.isdigit())
        valid_indian_number = (
            len(digits) == 10 and digits[0] in "6789"
        ) or (
            len(digits) == 12 and digits.startswith("91") and digits[2] in "6789"
        )
        if not valid_indian_number:
            raise ValueError("Enter a valid Indian phone number")
        return value.strip()

    @model_validator(mode="after")
    def validate_consent_and_contact(self):
        if not self.consent:
            raise ValueError("Privacy consent is required")
        if self.preferred_contact_method == "Email" and self.email is None:
            raise ValueError("Email is required when Email is the preferred contact method")
        return self


class EnquiryCreated(BaseModel):
    reference: str
    submitted_at: datetime
    status: Status
    fee_status: str
    message: str


class StatusUpdate(BaseModel):
    status: Status


class NoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_number: int
    student_name: str | None
    class_or_grade: str
    board: str
    academic_stream: str | None
    subjects: str | None
    tuition_type: str | None
    individual_monthly_fee: Decimal | None
    fee_status: str


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    note: str
    created_at: datetime


class EnquiryRead(BaseModel):
    id: UUID
    reference: str
    submitted_at: datetime
    parent_name: str
    phone: str
    email: str | None
    preferred_contact_method: str
    students_in_home: int
    city: str
    locality: str
    pin_code: str
    address: str | None
    tutor_gender_preference: str | None
    preferred_qualification: str | None
    teaching_language: str | None
    preferred_time: str | None
    classes_per_week: str | None
    session_duration: str | None
    additional_requirements: str | None
    consent: bool
    consent_timestamp: datetime
    privacy_notice_version: str
    individual_fee_subtotal: Decimal | None
    combined_monthly_fee: Decimal | None
    fee_status: str
    status: Status
    students: list[StudentRead]
    notes: list[NoteRead]


class EnquiryListItem(BaseModel):
    id: UUID
    reference: str
    submitted_at: datetime
    parent_name: str
    phone: str
    email: str | None
    students_in_home: int
    classes: list[str]
    subjects: list[str]
    combined_monthly_fee: Decimal | None
    fee_status: str
    status: Status


class EnquiryList(BaseModel):
    items: list[EnquiryListItem]
    total: int
    page: int
    page_size: int


class DashboardStats(BaseModel):
    total_enquiries: int
    new_enquiries: int
    contacted_parents: int
    follow_up_required: int
    converted_enquiries: int
    total_students: int


class StudentEstimateRequest(BaseModel):
    grade: str = Field(min_length=1, max_length=80)
    tuition_type: str | None = Field(default=None, max_length=40)


class FeeEstimateRequest(BaseModel):
    students: list[StudentEstimateRequest] = Field(min_length=1, max_length=10)
    classes_per_week: str | None = Field(default=None, max_length=30)
    session_duration: str | None = Field(default=None, max_length=40)


class StudentEstimateResult(BaseModel):
    grade: str
    base_fee: Decimal | None
    classes_multiplier: Decimal
    duration_multiplier: Decimal
    tuition_multiplier: Decimal
    estimated_fee: Decimal | None
    capped: bool
    status: str
    unavailable_reason: str | None


class FeeEstimateResponse(BaseModel):
    students: list[StudentEstimateResult]
    individual_subtotal: Decimal | None
    combined_monthly_fee: Decimal | None
    all_estimated: bool
    any_unavailable: bool
