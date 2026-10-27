from datetime import UTC, datetime

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import JWTSettings
from app.core.security import decode_token
from app.models import AuthSession, User
from app.modules.users.user import get_active_user


def get_authenticated_user(session: Session, access_token: str, settings: JWTSettings) -> User:
    """Check the JWT AND its live DB session; do not authorize from JWT role claims."""
    claims = decode_token(access_token, settings, expected_type="access")
    session_id = session.scalar(select(AuthSession.id).where(
        AuthSession.id == claims.session_id, AuthSession.user_id == claims.user_id,
        AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(UTC),
    ))
    if session_id is None:
        raise jwt.InvalidTokenError("Token session is not active")
    return get_active_user(session, claims.user_id)


# TODO protected endpoints: use api.dependencies.auth.get_current_user, which
# now supplies the request Session and maps auth failures to a generic 401.
# Business ownership/assignment checks remain separate.
