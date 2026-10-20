import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.database import get_session_factory
from app.models import Admin
from app.security import hash_password


def create_admin(email: str) -> int:
    normalized_email = email.strip().lower()
    if not normalized_email or "@" not in normalized_email or len(normalized_email) > 254:
        print("Enter a valid administrator email address.", file=sys.stderr)
        return 2

    db = get_session_factory()()
    try:
        existing = db.scalar(select(Admin).where(func.lower(Admin.email) == normalized_email))
        if existing:
            print("An administrator with that email already exists.", file=sys.stderr)
            return 2
        password = getpass.getpass("New admin password (minimum 12 characters): ")
        confirmation = getpass.getpass("Confirm admin password: ")
        if len(password) < 12:
            print("Password must be at least 12 characters.", file=sys.stderr)
            return 2
        if password != confirmation:
            print("Passwords do not match.", file=sys.stderr)
            return 2
        db.add(Admin(email=normalized_email, password_hash=hash_password(password), is_active=True))
        db.commit()
        print(f"Administrator account created for {normalized_email}. The password was not displayed.")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="REDDY ACADEMY administrator setup")
    subparsers = parser.add_subparsers(dest="command", required=True)
    admin_parser = subparsers.add_parser("create-admin", help="Securely create the first admin account")
    admin_parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.command == "create-admin":
        return create_admin(args.email)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
