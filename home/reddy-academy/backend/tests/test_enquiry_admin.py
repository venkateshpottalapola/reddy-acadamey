from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Admin, Base
from app.security import hash_password


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add(Admin(email="admin@example.com", password_hash=hash_password("test-password-long-123")))
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def valid_enquiry() -> dict:
    return {
        "idempotency_key": "req-0123456789abcdef012345",
        "parent_name": "Test Parent",
        "phone": "9885945863",
        "email": "parent@example.com",
        "preferred_contact_method": "Phone",
        "students": [
            {
                "student_name": "Student One",
                "grade": "Class 5",
                "board": "CBSE",
                "subjects": "Maths, English",
                "tuition_type": "One-to-one",
            },
            {
                "student_name": "Student Two",
                "grade": "Intermediate 1st Year",
                "board": "other",
                "custom_board": "Local curriculum",
                "stream": "Science",
                "subjects": "Physics",
            },
        ],
        "tutor_gender": "No preference",
        "qualification": "Mathematics",
        "language": "English, Telugu",
        "preferred_time": "Evening",
        "classes_per_week": "3 classes",
        "session_duration": "1.5 hours",
        "city": "Hyderabad",
        "locality": "Madhapur",
        "pin_code": "500081",
        "address": "Test address",
        "message": "=1+1",
        "consent": True,
    }


def admin_csrf(client: TestClient) -> str:
    response = client.get("/api/admin/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def admin_login(client: TestClient) -> str:
    csrf = admin_csrf(client)
    response = client.post(
        "/api/admin/login",
        headers={"X-CSRF-Token": csrf},
        json={"email": "admin@example.com", "password": "test-password-long-123"},
    )
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_enquiry_persists_multiple_students_and_admin_manages_privately(client: TestClient) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "database": "connected"}
    assert client.get("/admin/login").status_code == 200

    payload = valid_enquiry()
    public_response = client.post("/api/enquiries", json=payload)
    assert public_response.status_code == 201, public_response.text
    saved = public_response.json()
    assert saved["reference"].startswith("RA-")
    assert saved["status"] == "New"
    assert saved["fee_status"] == "unavailable"

    repeat_response = client.post("/api/enquiries", json=payload)
    assert repeat_response.status_code == 201
    assert repeat_response.json()["reference"] == saved["reference"]

    assert client.get("/api/admin/enquiries").status_code == 401
    assert client.get("/api/admin/dashboard").status_code == 401
    dashboard_page = client.get("/admin/dashboard", follow_redirects=False)
    assert dashboard_page.status_code == 303
    assert dashboard_page.headers["location"] == "/admin/login"
    csrf = admin_login(client)
    assert client.get("/api/admin/me").status_code == 200
    assert client.get("/admin/dashboard", follow_redirects=False).status_code == 200
    stats = client.get("/api/admin/dashboard").json()
    assert stats == {
        "total_enquiries": 1,
        "new_enquiries": 1,
        "contacted_parents": 0,
        "follow_up_required": 0,
        "converted_enquiries": 0,
        "total_students": 2,
    }

    listing = client.get("/api/admin/enquiries?search=Test%20Parent").json()
    assert listing["total"] == 1
    assert listing["items"][0]["students_in_home"] == 2
    enquiry_id = listing["items"][0]["id"]
    detail_response = client.get(f"/api/admin/enquiries/{enquiry_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert [student["student_name"] for student in detail["students"]] == ["Student One", "Student Two"]
    assert detail["students"][1]["board"] == "Local curriculum"
    assert detail["individual_fee_subtotal"] is None
    assert detail["additional_requirements"] == "=1+1"

    assert client.patch(
        f"/api/admin/enquiries/{enquiry_id}/status",
        json={"status": "Contacted"},
    ).status_code == 403
    status_response = client.patch(
        f"/api/admin/enquiries/{enquiry_id}/status",
        headers={"X-CSRF-Token": csrf},
        json={"status": "Follow-up Required"},
    )
    assert status_response.status_code == 200
    assert client.get("/api/admin/enquiries?status=Follow-up%20Required").json()["total"] == 1
    assert client.get("/api/admin/dashboard").json()["follow_up_required"] == 1

    note_response = client.post(
        f"/api/admin/enquiries/{enquiry_id}/notes",
        headers={"X-CSRF-Token": csrf},
        json={"note": "Call the parent after 6 pm."},
    )
    assert note_response.status_code == 201
    assert "Call the parent" in client.get(f"/api/admin/enquiries/{enquiry_id}").text

    csv_response = client.get("/api/admin/enquiries/export.csv")
    assert csv_response.status_code == 200
    assert "'=1+1" in csv_response.text

    logout_response = client.post("/api/admin/logout", headers={"X-CSRF-Token": csrf})
    assert logout_response.status_code == 200
    assert client.get("/api/admin/enquiries").status_code == 401


def test_enquiry_validation_rejects_missing_consent_or_custom_board(client: TestClient) -> None:
    payload = valid_enquiry()
    payload["consent"] = False
    assert client.post("/api/enquiries", json=payload).status_code == 422

    payload = valid_enquiry()
    payload["students"][1]["custom_board"] = None
    assert client.post("/api/enquiries", json=payload).status_code == 422
