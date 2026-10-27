from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
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
