from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models import AuthSession


def revoke_token_session(session: Session, session_id: UUID, user_id: UUID) -> None:
    """Idempotent logout; identity/session ID must come from a validated access JWT."""
    session.execute(update(AuthSession).where(
        AuthSession.id == session_id, AuthSession.user_id == user_id,
        AuthSession.revoked_at.is_(None),
    ).values(revoked_at=datetime.now(UTC)).execution_options(synchronize_session=False))
    session.flush()


# TODO logout endpoint: validate access/session first, then commit revocation;
# never accept arbitrary user_id from a request body as authenticated identity.
# TODO logout_all/password_reset: revoke all user sessions transactionally.


def cleanup_expired_sessions(session: Session, admin_id: UUID, *, retention_days: int = 30) -> int:
    from app.models.enums import UserRole
    from app.modules.users.action_log import record_admin_action
    from app.modules.users.user import get_active_user

    admin = get_active_user(session, admin_id)
    if admin.role not in {UserRole.ADMIN, UserRole.HEAD_ADMIN}:
        raise PermissionError("Administrator role required")
    if retention_days < 30:
        raise ValueError("Keep at least 30 days of expired session history")
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    result = session.execute(delete(AuthSession).where(AuthSession.expires_at <= cutoff)
                             .execution_options(synchronize_session=False))
    count = result.rowcount
    record_admin_action(session, admin_id=admin.id, action_code="auth.cleanup", target_type="users",
                        target_id=admin.id, reason="Remove sessions expired more than 30 days ago",
                        new_value={"revoked_sessions": count})
    return count
