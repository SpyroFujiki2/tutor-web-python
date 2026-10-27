from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import JWTSettings, get_jwt_settings
from app.core.security import TokenClaims, decode_token
from app.api.dependencies.database import get_session
from app.models import User
from app.modules.auth.current_user import get_authenticated_user

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="JWTBearer", bearerFormat="JWT")


def get_access_claims(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[JWTSettings, Depends(get_jwt_settings)],
) -> TokenClaims:
    """Only validates JWT claims. Protected routes must ALSO check DB session/user."""
    if credentials is not None and credentials.scheme.lower() == "bearer":
        try:
            return decode_token(credentials.credentials, settings, expected_type="access")
        except jwt.InvalidTokenError:
            pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[JWTSettings, Depends(get_jwt_settings)],
) -> User:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        try:
            return get_authenticated_user(session, credentials.credentials, settings)
        except (jwt.InvalidTokenError, LookupError, PermissionError):
            pass
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing bearer token",
        headers={"WWW-Authenticate": "Bearer"},
    )
