import csv
import io
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.config import FRONTEND_DIR, get_settings
from app.database import get_db
from app.models import Admin, AdminSession, Enquiry, EnquiryNote, Student, utc_now
from app.pricing import estimate_student_fee
from app.schemas import (
    DashboardStats,
    EnquiryCreate,
    EnquiryCreated,
    EnquiryList,
    EnquiryListItem,
    EnquiryRead,
    NoteCreate,
    NoteRead,
    Status,
    FeeEstimateRequest,
    FeeEstimateResponse,
    StudentEstimateResult,
    StatusUpdate,
)
from app.security import (
    check_login_rate_limit,
    clear_admin_cookies,
    get_current_admin,
    issue_csrf_cookie,
    make_admin_session,
    require_admin_csrf,
    require_login_csrf,
    reset_login_rate_limit,
    revoke_admin_session,
    set_admin_cookies,
    verify_password,
)


public_router = APIRouter(prefix="/api")
@public_router.post("/fees/estimate", response_model=FeeEstimateResponse)
def estimate_fees(payload: FeeEstimateRequest) -> FeeEstimateResponse:
    from decimal import Decimal
    results = []
    for student in payload.students:
        r = estimate_student_fee(
            grade=student.grade,
            classes_per_week=payload.classes_per_week,
            session_duration=payload.session_duration,
            tuition_type=student.tuition_type,
        )
        results.append(StudentEstimateResult(
            grade=r.grade,
            base_fee=r.base_fee,
            classes_multiplier=r.classes_multiplier,
            duration_multiplier=r.duration_multiplier,
            tuition_multiplier=r.tuition_multiplier,
            estimated_fee=r.estimated_fee,
            capped=r.capped,
            status=r.status,
            unavailable_reason=r.unavailable_reason,
        ))
    any_unavailable = any(r.status == "unavailable" for r in results)
    all_estimated = all(r.status == "estimated" for r in results)
    estimated_fees = [r.estimated_fee for r in results if r.estimated_fee is not None]
    individual_subtotal = sum(estimated_fees, Decimal("0")) if estimated_fees else None
    combined_monthly_fee = individual_subtotal
    return FeeEstimateResponse(
        students=results,
        individual_subtotal=individual_subtotal,
        combined_monthly_fee=combined_monthly_fee,
        all_estimated=all_estimated,
        any_unavailable=any_unavailable,
    )

admin_router = APIRouter(prefix="/api/admin")
VALID_STATUSES: tuple[Status, ...] = ("New", "Contacted", "Follow-up Required", "Converted", "Closed")


@public_router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(select(1))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable.") from exc
    return {"status": "ok", "database": "connected"}


@public_router.post("/enquiries", response_model=EnquiryCreated, status_code=201)
def create_enquiry(payload: EnquiryCreate, db: Session = Depends(get_db)) -> EnquiryCreated:
    existing = db.scalar(select(Enquiry).where(Enquiry.idempotency_key == payload.idempotency_key))
    if existing:
        return EnquiryCreated(
            reference=existing.reference,
            submitted_at=existing.submitted_at,
            status=existing.status,
            fee_status=existing.fee_status,
            message="This enquiry was already received.",
        )

    submitted_at = utc_now()
    reference = f"RA-{submitted_at:%Y%m%d}-{secrets.token_hex(4).upper()}"
    settings = get_settings()
    enquiry = Enquiry(
        reference=reference,
        idempotency_key=payload.idempotency_key,
        parent_name=payload.parent_name.strip(),
        phone=payload.phone.strip(),
        email=str(payload.email) if payload.email else None,
        preferred_contact_method=payload.preferred_contact_method,
        students_in_home=len(payload.students),
        city=payload.city.strip(),
        locality=payload.locality.strip(),
        pin_code=payload.pin_code,
        address=payload.address.strip() if payload.address else None,
        tutor_gender_preference=payload.tutor_gender or None,
        preferred_qualification=payload.qualification.strip() if payload.qualification else None,
        teaching_language=payload.language.strip() if payload.language else None,
        preferred_time=payload.preferred_time or None,
        classes_per_week=payload.classes_per_week or None,
        session_duration=payload.session_duration or None,
        additional_requirements=payload.message.strip() if payload.message else None,
        consent=True,
        consent_timestamp=submitted_at,
        privacy_notice_version=settings.privacy_notice_version,
        fee_status="unavailable",
        status="New",
        submitted_at=submitted_at,
    )
    for index, student_data in enumerate(payload.students, start=1):
        board = student_data.custom_board.strip() if student_data.board == "other" else student_data.board
        enquiry.students.append(
            Student(
                student_number=index,
                student_name=student_data.student_name.strip() if student_data.student_name else None,
                class_or_grade=student_data.grade,
                board=board,
                academic_stream=student_data.stream or None,
                subjects=student_data.subjects.strip() if student_data.subjects else None,
                tuition_type=student_data.tuition_type or None,
                individual_monthly_fee=None,
                fee_status="unavailable",
            )
        )

    db.add(enquiry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Enquiry).where(Enquiry.idempotency_key == payload.idempotency_key))
        if existing:
            return EnquiryCreated(
                reference=existing.reference,
                submitted_at=existing.submitted_at,
                status=existing.status,
                fee_status=existing.fee_status,
                message="This enquiry was already received.",
            )
        raise HTTPException(status_code=409, detail="The enquiry could not be saved due to a conflicting request.")
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="The enquiry could not be saved. Please try again later.") from exc

    return EnquiryCreated(
        reference=enquiry.reference,
        submitted_at=enquiry.submitted_at,
        status=enquiry.status,
        fee_status=enquiry.fee_status,
        message="Your enquiry was saved successfully.",
    )


@public_router.get("/admin/csrf")
def admin_csrf(response: Response) -> dict[str, str]:
    return {"csrf_token": issue_csrf_cookie(response)}


@public_router.post("/admin/login")
async def admin_login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    require_login_csrf(request)
    check_login_rate_limit(request)
    try:
        body = await _read_login_payload(request)
        email = body["email"].strip().lower()
        password = body["password"]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Enter a valid email and password.")
    admin = db.scalar(select(Admin).where(func.lower(Admin.email) == email))
    if admin is None or not admin.is_active or not verify_password(admin.password_hash, password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    reset_login_rate_limit(request)
    raw_token, csrf_token, ttl = make_admin_session(db, admin)
    set_admin_cookies(response, raw_token, csrf_token, ttl)
    return {"email": admin.email, "csrf_token": csrf_token}


async def _read_login_payload(request: Request) -> dict:
    body = await request.json()
    if not isinstance(body, dict):
        raise ValueError("Expected JSON object")
    email, password = body.get("email"), body.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not 1 <= len(password) <= 1024:
        raise ValueError("Invalid login fields")
    return {"email": email[:254], "password": password}


@admin_router.post("/logout")
def admin_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_admin_csrf),
) -> dict[str, str]:
    revoke_admin_session(db, request.cookies.get("reddy_admin_session"))
    clear_admin_cookies(response)
    return {"message": "Logged out."}


@admin_router.get("/me")
def admin_me(
    request: Request,
    admin: Admin = Depends(get_current_admin),
) -> dict[str, str | None]:
    stored_session: AdminSession = request.state.admin_session
    return {"email": admin.email, "csrf_token": stored_session.csrf_token}


@admin_router.get("/dashboard", response_model=DashboardStats)
def admin_dashboard(
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
) -> DashboardStats:
    counts = dict(
        db.query(Enquiry.status, func.count(Enquiry.id)).group_by(Enquiry.status).all()
    )
    return DashboardStats(
        total_enquiries=sum(counts.values()),
        new_enquiries=counts.get("New", 0),
        contacted_parents=counts.get("Contacted", 0),
        follow_up_required=counts.get("Follow-up Required", 0),
        converted_enquiries=counts.get("Converted", 0),
        total_students=db.scalar(select(func.count(Student.id))) or 0,
    )


def _filtered_enquiries(
    db: Session,
    search: str | None,
    status: Status | None,
    submitted_from: date | None,
    submitted_to: date | None,
):
    query = select(Enquiry).options(joinedload(Enquiry.students)).order_by(Enquiry.submitted_at.desc())
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(Enquiry.parent_name.ilike(term), Enquiry.phone.ilike(term)))
    if status:
        query = query.where(Enquiry.status == status)
    if submitted_from:
        query = query.where(Enquiry.submitted_at >= datetime.combine(submitted_from, time.min, timezone.utc))
    if submitted_to:
        day_after = submitted_to + timedelta(days=1)
        query = query.where(Enquiry.submitted_at < datetime.combine(day_after, time.min, timezone.utc))
    return query


def _list_item(enquiry: Enquiry) -> EnquiryListItem:
    return EnquiryListItem(
        id=enquiry.id,
        reference=enquiry.reference,
        submitted_at=enquiry.submitted_at,
        parent_name=enquiry.parent_name,
        phone=enquiry.phone,
        email=enquiry.email,
        students_in_home=enquiry.students_in_home,
        classes=[student.class_or_grade for student in enquiry.students],
        subjects=[student.subjects or "" for student in enquiry.students],
        combined_monthly_fee=enquiry.combined_monthly_fee,
        fee_status=enquiry.fee_status,
        status=enquiry.status,
    )


@admin_router.get("/enquiries", response_model=EnquiryList)
def admin_enquiries(
    search: str | None = Query(default=None, max_length=120),
    status: Status | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
) -> EnquiryList:
    if submitted_from and submitted_to and submitted_from > submitted_to:
        raise HTTPException(status_code=422, detail="Start date must be on or before end date.")
    filtered = _filtered_enquiries(db, search, status, submitted_from, submitted_to)
    total = db.scalar(select(func.count()).select_from(filtered.order_by(None).subquery())) or 0
    records = db.scalars(filtered.offset((page - 1) * page_size).limit(page_size)).unique().all()
    return EnquiryList(items=[_list_item(record) for record in records], total=total, page=page, page_size=page_size)


@admin_router.get("/enquiries/export.csv")
def export_enquiries(
    search: str | None = Query(default=None, max_length=120),
    status: Status | None = None,
    submitted_from: date | None = None,
    submitted_to: date | None = None,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
) -> StreamingResponse:
    if submitted_from and submitted_to and submitted_from > submitted_to:
        raise HTTPException(status_code=422, detail="Start date must be on or before end date.")
    records = db.scalars(
        _filtered_enquiries(db, search, status, submitted_from, submitted_to)
    ).unique().all()
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Reference", "Submitted at", "Parent name", "Phone", "Email", "Student count",
            "Classes", "Boards", "Subjects", "Individual fee subtotal", "Estimated monthly fee",
            "Fee status", "Status", "Message",
        ]
    )
    for record in records:
        values = [
            record.reference,
            record.submitted_at.isoformat(),
            record.parent_name,
            record.phone,
            record.email or "",
            record.students_in_home,
            "; ".join(student.class_or_grade for student in record.students),
            "; ".join(student.board for student in record.students),
            "; ".join(student.subjects or "" for student in record.students),
            record.individual_fee_subtotal if record.individual_fee_subtotal is not None else "",
            record.combined_monthly_fee if record.combined_monthly_fee is not None else "",
            record.fee_status,
            record.status,
            record.additional_requirements or "",
        ]
        writer.writerow([_spreadsheet_safe(value) for value in values])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="reddy-academy-enquiries.csv"'},
    )


def _spreadsheet_safe(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@admin_router.get("/enquiries/{enquiry_id}", response_model=EnquiryRead)
def admin_enquiry_detail(
    enquiry_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(get_current_admin),
) -> Enquiry:
    enquiry = db.scalar(
        select(Enquiry)
        .options(joinedload(Enquiry.students), joinedload(Enquiry.notes))
        .where(Enquiry.id == enquiry_id)
    )
    if enquiry is None:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    return enquiry


@admin_router.patch("/enquiries/{enquiry_id}/status")
def update_enquiry_status(
    enquiry_id: uuid.UUID,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_admin_csrf),
) -> dict[str, str]:
    enquiry = db.get(Enquiry, enquiry_id)
    if enquiry is None:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    enquiry.status = payload.status
    enquiry.updated_at = utc_now()
    db.commit()
    return {"status": enquiry.status}


@admin_router.post("/enquiries/{enquiry_id}/notes", response_model=NoteRead, status_code=201)
def add_internal_note(
    enquiry_id: uuid.UUID,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_admin_csrf),
) -> EnquiryNote:
    enquiry = db.get(Enquiry, enquiry_id)
    if enquiry is None:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    note = EnquiryNote(enquiry_id=enquiry.id, admin_id=admin.id, note=payload.note.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@admin_router.delete("/enquiries/{enquiry_id}", status_code=204)
def delete_enquiry(
    enquiry_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: Admin = Depends(require_admin_csrf),
) -> Response:
    enquiry = db.get(Enquiry, enquiry_id)
    if enquiry is None:
        raise HTTPException(status_code=404, detail="Enquiry not found.")
    db.delete(enquiry)
    db.commit()
    return Response(status_code=204)
