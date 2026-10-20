"""Create admin, enquiry, student, note and session tables.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True)
    op.create_table(
        "admins",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admins_email", "admins", ["email"], unique=True)
    op.create_table(
        "enquiries",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("parent_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("preferred_contact_method", sa.String(20), nullable=False),
        sa.Column("students_in_home", sa.Integer(), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("locality", sa.String(120), nullable=False),
        sa.Column("pin_code", sa.String(6), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("tutor_gender_preference", sa.String(40), nullable=True),
        sa.Column("preferred_qualification", sa.String(120), nullable=True),
        sa.Column("teaching_language", sa.String(80), nullable=True),
        sa.Column("preferred_time", sa.String(40), nullable=True),
        sa.Column("classes_per_week", sa.String(30), nullable=True),
        sa.Column("session_duration", sa.String(40), nullable=True),
        sa.Column("additional_requirements", sa.String(1000), nullable=True),
        sa.Column("consent", sa.Boolean(), nullable=False),
        sa.Column("consent_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("privacy_notice_version", sa.String(40), nullable=False),
        sa.Column("individual_fee_subtotal", sa.Numeric(10, 2), nullable=True),
        sa.Column("combined_monthly_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("fee_status", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_enquiries_idempotency_key"),
    )
    op.create_index("ix_enquiries_reference", "enquiries", ["reference"], unique=True)
    op.create_index("ix_enquiries_idempotency_key", "enquiries", ["idempotency_key"])
    op.create_index("ix_enquiries_phone", "enquiries", ["phone"])
    op.create_index("ix_enquiries_city", "enquiries", ["city"])
    op.create_index("ix_enquiries_locality", "enquiries", ["locality"])
    op.create_index("ix_enquiries_status", "enquiries", ["status"])
    op.create_index("ix_enquiries_created_status", "enquiries", ["submitted_at", "status"])
    op.create_table(
        "admin_sessions",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("admin_id", uuid_type, sa.ForeignKey("admins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_sessions_admin_id", "admin_sessions", ["admin_id"])
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"], unique=True)
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])
    op.create_table(
        "students",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("enquiry_id", uuid_type, sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_number", sa.Integer(), nullable=False),
        sa.Column("student_name", sa.String(120), nullable=True),
        sa.Column("class_or_grade", sa.String(80), nullable=False),
        sa.Column("board", sa.String(100), nullable=False),
        sa.Column("academic_stream", sa.String(80), nullable=True),
        sa.Column("subjects", sa.String(300), nullable=True),
        sa.Column("tuition_type", sa.String(40), nullable=True),
        sa.Column("individual_monthly_fee", sa.Numeric(10, 2), nullable=True),
        sa.Column("fee_status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("enquiry_id", "student_number", name="uq_student_number_per_enquiry"),
    )
    op.create_index("ix_students_enquiry_id", "students", ["enquiry_id"])
    op.create_table(
        "enquiry_notes",
        sa.Column("id", uuid_type, primary_key=True, nullable=False),
        sa.Column("enquiry_id", uuid_type, sa.ForeignKey("enquiries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("admin_id", uuid_type, sa.ForeignKey("admins.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enquiry_notes_enquiry_id", "enquiry_notes", ["enquiry_id"])


def downgrade() -> None:
    op.drop_index("ix_enquiry_notes_enquiry_id", table_name="enquiry_notes")
    op.drop_table("enquiry_notes")
    op.drop_index("ix_students_enquiry_id", table_name="students")
    op.drop_table("students")
    op.drop_index("ix_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_token_hash", table_name="admin_sessions")
    op.drop_index("ix_admin_sessions_admin_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index("ix_enquiries_created_status", table_name="enquiries")
    op.drop_index("ix_enquiries_status", table_name="enquiries")
    op.drop_index("ix_enquiries_locality", table_name="enquiries")
    op.drop_index("ix_enquiries_city", table_name="enquiries")
    op.drop_index("ix_enquiries_phone", table_name="enquiries")
    op.drop_index("ix_enquiries_idempotency_key", table_name="enquiries")
    op.drop_index("ix_enquiries_reference", table_name="enquiries")
    op.drop_table("enquiries")
    op.drop_index("ix_admins_email", table_name="admins")
    op.drop_table("admins")
