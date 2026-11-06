from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_access_claims, get_current_user
from app.api.dependencies.database import get_session
from app.core.config import JWTSettings, get_jwt_settings
from app.core.security import TokenClaims
from app.models import User
from app.modules.auth.authenticate import authenticate_user
from app.modules.auth.login import issue_login_tokens
from app.modules.auth.logout import cleanup_expired_sessions, revoke_token_session
from app.modules.auth.refresh import renew_tokens
from app.schemas.auth import CurrentUserResponse, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.auth import AuthSessionResponse, ChangeEmailRequest, ChangePasswordRequest, RegisterRequest
from app.modules.users.accounts import change_email, change_password, list_sessions, register_user, revoke_all, revoke_session

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDependency = Annotated[Session, Depends(get_session)]
JWTDependency = Annotated[JWTSettings, Depends(get_jwt_settings)]


def limit_login_attempts(request: Request) -> None:
    client = request.client.host if request.client is not None else "unknown"
    retry_after = request.app.state.login_rate_limiter.consume(client)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limit_login_attempts)])
def login(
    payload: LoginRequest, response: Response, session: SessionDependency, settings: JWTDependency,
) -> TokenResponse:
    with session.begin():
        user_id = authenticate_user(session, str(payload.email), payload.password.get_secret_value())
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        tokens = issue_login_tokens(session, user_id, settings)
        result = TokenResponse.model_validate(tokens, from_attributes=True)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest, response: Response, session: SessionDependency, settings: JWTDependency,
) -> TokenResponse:
    with session.begin():
        renewal = renew_tokens(session, payload.refresh_token.get_secret_value(), settings)
        result = (
            TokenResponse.model_validate(renewal.tokens, from_attributes=True)
            if renewal.tokens is not None else None
        )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return result


@router.get("/me", response_model=CurrentUserResponse)
def me(
    response: Response, user: Annotated[User, Depends(get_current_user)],
) -> CurrentUserResponse:
    response.headers["Cache-Control"] = "no-store"
    return CurrentUserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: SessionDependency,
    user: Annotated[User, Depends(get_current_user)],
    claims: Annotated[TokenClaims, Depends(get_access_claims)],
) -> Response:
    revoke_token_session(session, claims.session_id, user.id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.post("/register", response_model=CurrentUserResponse, status_code=201,
             dependencies=[Depends(limit_login_attempts)])
def register(payload: RegisterRequest, session: SessionDependency, response: Response):
    with session.begin():
        user = register_user(session, payload.email, payload.password.get_secret_value())
        result = CurrentUserResponse.model_validate(user)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.post("/change-password", status_code=204, dependencies=[Depends(limit_login_attempts)])
def password_change(payload: ChangePasswordRequest, session: SessionDependency,
                    user: Annotated[User, Depends(get_current_user)]):
    change_password(session, user.id, payload.old_password.get_secret_value(), payload.new_password.get_secret_value())
    session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/logout-all", status_code=204)
def logout_all(session: SessionDependency, user: Annotated[User, Depends(get_current_user)]):
    revoke_all(session, user.id)
    session.commit()
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/change-email", response_model=CurrentUserResponse, dependencies=[Depends(limit_login_attempts)])
def email_change(payload: ChangeEmailRequest, session: SessionDependency,
                 user: Annotated[User, Depends(get_current_user)]):
    updated = change_email(session, user.id, payload.password.get_secret_value(), payload.email)
    result = CurrentUserResponse.model_validate(updated)
    session.commit()
    return result


@router.get("/sessions", response_model=list[AuthSessionResponse])
def active_sessions(session: SessionDependency, user: Annotated[User, Depends(get_current_user)],
                    claims: Annotated[TokenClaims, Depends(get_access_claims)]):
    return [AuthSessionResponse(id=row.id, created_at=row.created_at, expires_at=row.expires_at,
                                is_current=row.id == claims.session_id) for row in list_sessions(session, user.id)]


@router.post("/sessions/{session_id}/revoke", status_code=204)
def session_revoke(session_id: UUID, session: SessionDependency,
                   user: Annotated[User, Depends(get_current_user)]):
    revoke_session(session, user.id, session_id)
    session.commit()
    return Response(status_code=204)


@router.post("/admin/cleanup-sessions")
def cleanup_sessions(session: SessionDependency, user: Annotated[User, Depends(get_current_user)]):
    count = cleanup_expired_sessions(session, user.id)
    session.commit()
    return {"deleted": count}
