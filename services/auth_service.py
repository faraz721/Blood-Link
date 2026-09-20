from datetime import datetime, timedelta
from typing import Optional, Tuple
from models import db, User, AdminUser, LoginAttempt
from config.settings import Config


def is_blocked(identifier: str, attempt_type: str = "donor") -> Tuple[bool, Optional[str]]:
    """Check if identifier is currently blocked. Returns (blocked, message)."""
    record = LoginAttempt.query.filter_by(
        identifier=identifier, attempt_type=attempt_type
    ).first()
    if not record or not record.blocked_until:
        return False, None
    if record.blocked_until > datetime.utcnow():
        remaining = int((record.blocked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return True, f"Too many failed attempts. Please try again in {remaining} minute(s)."
    # Block expired – reset
    record.failed_count = 0
    record.blocked_until = None
    db.session.commit()
    return False, None


def record_failed_attempt(identifier: str, attempt_type: str = "donor") -> None:
    record = LoginAttempt.query.filter_by(
        identifier=identifier, attempt_type=attempt_type
    ).first()
    if not record:
        record = LoginAttempt(identifier=identifier, attempt_type=attempt_type, failed_count=0)
        db.session.add(record)

    record.failed_count += 1
    record.last_attempt = datetime.utcnow()

    if record.failed_count >= Config.MAX_FAILED_LOGINS:
        record.blocked_until = datetime.utcnow() + timedelta(minutes=Config.LOCKOUT_MINUTES)

    db.session.commit()


def clear_failed_attempts(identifier: str, attempt_type: str = "donor") -> None:
    record = LoginAttempt.query.filter_by(
        identifier=identifier, attempt_type=attempt_type
    ).first()
    if record:
        record.failed_count = 0
        record.blocked_until = None
        db.session.commit()


def authenticate_donor(phone: str, password: str) -> Tuple[Optional[User], str]:
    """
    Authenticate donor. Returns (user, error_message).
    Always returns generic error on failure.
    """
    from services.phone_service import normalize_phone

    normalized = normalize_phone(phone)
    if not normalized:
        return None, "Invalid phone number or password."

    blocked, msg = is_blocked(normalized, "donor")
    if blocked:
        return None, msg

    user = User.query.filter_by(phone=normalized, role="donor").first()
    if not user or not user.check_password(password):
        record_failed_attempt(normalized, "donor")
        return None, "Invalid phone number or password."

    if user.is_suspended:
        return None, "Your account has been suspended. Please contact support."

    if not user.is_active:
        return None, "Your account is inactive."

    clear_failed_attempts(normalized, "donor")
    return user, ""


def authenticate_admin(username: str, password: str) -> Tuple[Optional[AdminUser], str]:
    blocked, msg = is_blocked(username.lower(), "admin")
    if blocked:
        return None, msg

    admin = AdminUser.query.filter_by(username=username).first()
    if not admin or not admin.check_password(password):
        record_failed_attempt(username.lower(), "admin")
        return None, "Invalid username or password."

    clear_failed_attempts(username.lower(), "admin")
    return admin, ""