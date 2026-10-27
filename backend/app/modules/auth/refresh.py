from datetime import UTC, datetime

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import JWTSettings
from app.core.security import RenewalResult, create_token_pair, decode_token, hash_refresh_token
from app.models import AuthSession
from app.modules.users.user import get_active_user


def renew_tokens(session: Session, refresh_token: str, settings: JWTSettings) -> RenewalResult:
    """Rotate once. Commit even a denied result BEFORE mapping it to HTTP 401."""
    try:
        claims = decode_token(refresh_token, settings, expected_type="refresh")
    except jwt.InvalidTokenError:
        return RenewalResult(error="invalid")
    record = session.scalar(select(AuthSession).where(
        AuthSession.id == claims.session_id, AuthSession.user_id == claims.user_id,
    ).execution_options(populate_existing=True))
    if record is None or record.revoked_at is not None:
        return RenewalResult(error="revoked")
    now = datetime.now(UTC)
    expiry = record.expires_at.replace(tzinfo=UTC) if record.expires_at.tzinfo is None else record.expires_at
    if expiry <= now:
        return RenewalResult(error="expired")
    try:
        get_active_user(session, claims.user_id)
    except (LookupError, PermissionError):
        session.execute(update(AuthSession).where(AuthSession.id == record.id).values(revoked_at=now))
        session.flush()
        return RenewalResult(error="user_inactive")
    tokens = create_token_pair(claims.user_id, claims.session_id, settings, refresh_expires_at=expiry)
    # A conditional UPDATE makes consumption atomic, even across multiple workers.
    changed = session.execute(
        update(AuthSession).where(
            AuthSession.id == claims.session_id,
            AuthSession.user_id == claims.user_id,
            AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
            AuthSession.revoked_at.is_(None), AuthSession.expires_at > now,
        ).values(refresh_token_hash=hash_refresh_token(tokens.refresh_token))
        .returning(AuthSession.id).execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if changed is None:
        # Reusing an old signed refresh revokes this entire token family.
        session.execute(update(AuthSession).where(
            AuthSession.id == claims.session_id, AuthSession.revoked_at.is_(None),
        ).values(revoked_at=now).execution_options(synchronize_session=False))
        session.flush()
        return RenewalResult(error="reused")
    session.flush()
    return RenewalResult(tokens=tokens)


# TODO refresh endpoint: use this result outside session.begin(), so replay
# revocation is committed before raising 401. Client must serialize refresh calls.
# TODO production: run concurrent UPDATE/replay tests on PostgreSQL; register the
# route using the existing get_session dependency after its response schema is ready.
