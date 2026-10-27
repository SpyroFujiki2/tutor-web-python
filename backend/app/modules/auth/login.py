from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.config import JWTSettings
from app.core.security import TokenPair, create_token_pair, decode_token, hash_refresh_token
from app.models import AuthSession
from app.modules.users.user import get_active_user


def issue_login_tokens(session: Session, user_id: UUID, settings: JWTSettings) -> TokenPair:
    """Only call AFTER password/MFA verification; user_id alone is not authentication."""
    get_active_user(session, user_id)
    session_id = uuid4()
    tokens = create_token_pair(user_id, session_id, settings)
    refresh = decode_token(tokens.refresh_token, settings, expected_type="refresh")
    session.add(AuthSession(
        id=session_id, user_id=user_id, refresh_token_hash=hash_refresh_token(tokens.refresh_token),
        created_at=datetime.now(UTC).replace(microsecond=0), expires_at=refresh.expires_at,
    ))
    session.flush()
    return tokens


# TODO login endpoint: verify credentials first, then commit AuthSession before
# returning tokens; apply rate limits and generic errors for failed credentials.
