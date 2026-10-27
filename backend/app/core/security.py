"""Argon2 passwords and JWT primitives; persistence/rotation lives in modules/auth."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Literal
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import JWTSettings

_password_hasher = PasswordHash.recommended()
TokenType = Literal["access", "refresh"]


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    session_id: UUID
    token_id: UUID
    token_type: TokenType
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    refresh_expires_in: int
    token_type: Literal["bearer"] = "bearer"


@dataclass(frozen=True)
class RenewalResult:
    # A denial may have revoked a compromised session: COMMIT before returning 401.
    tokens: TokenPair | None = field(default=None, repr=False)
    error: Literal["invalid", "revoked", "expired", "reused", "user_inactive"] | None = None


def hash_password(password: str) -> str:
    """Tạo hash Argon2id có salt riêng để lưu vào users.password_hash."""
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    if not password:
        raise ValueError("Password must not be empty")
    # Không strip/normalize: mật khẩu phải giữ nguyên ký tự người dùng đã nhập.
    return _password_hasher.hash(password)


def create_token_pair(
    user_id: UUID,
    session_id: UUID,
    settings: JWTSettings,
    *,
    refresh_expires_at: datetime | None = None,
) -> TokenPair:
    """Sign a pair; caller must persist a session before returning it to a client."""
    now = datetime.now(UTC).replace(microsecond=0)
    if refresh_expires_at is None:
        refresh_expires_at = now + timedelta(seconds=settings.refresh_ttl_seconds)
    if refresh_expires_at.tzinfo is None:
        raise ValueError("Refresh expiry must be timezone-aware")
    refresh_expires_at = refresh_expires_at.astimezone(UTC).replace(microsecond=0)
    if refresh_expires_at <= now:
        raise ValueError("Refresh session has expired")
    # Renew never extends the original login session's absolute expiry.
    access_expires_at = min(now + timedelta(seconds=settings.access_ttl_seconds), refresh_expires_at)
    tokens = {}
    for kind, expires_at in (("access", access_expires_at), ("refresh", refresh_expires_at)):
        tokens[kind] = jwt.encode(
            {
                "sub": str(user_id), "sid": str(session_id), "jti": str(uuid4()),
                "type": kind, "iss": settings.issuer, "aud": settings.audience,
                "iat": int(now.timestamp()), "nbf": int(now.timestamp()), "exp": int(expires_at.timestamp()),
            },
            settings.secret_key,
            algorithm="HS256",
            headers={"typ": "at+jwt" if kind == "access" else "rt+jwt"},
        )
    return TokenPair(
        access_token=tokens["access"], refresh_token=tokens["refresh"],
        expires_in=int((access_expires_at - now).total_seconds()),
        refresh_expires_in=int((refresh_expires_at - now).total_seconds()),
    )


def decode_token(token: str, settings: JWTSettings, *, expected_type: TokenType) -> TokenClaims:
    """Validate signed claims; this does NOT replace the DB session/user check."""
    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=["HS256"],
        issuer=settings.issuer,
        audience=settings.audience,
        options={
            "require": ["sub", "sid", "jti", "type", "iss", "aud", "iat", "nbf", "exp"],
            "strict_aud": True,
        },
    )
    expected_header = "at+jwt" if expected_type == "access" else "rt+jwt"
    if payload["type"] != expected_type or jwt.get_unverified_header(token).get("typ") != expected_header:
        raise jwt.InvalidTokenError("Wrong token type")
    if any(type(payload[key]) is not int for key in ("iat", "nbf", "exp")):
        raise jwt.InvalidTokenError("Invalid token timestamps")
    if not payload["iat"] <= payload["nbf"] < payload["exp"]:
        raise jwt.InvalidTokenError("Invalid token lifetime")
    try:
        return TokenClaims(
            user_id=UUID(payload["sub"]), session_id=UUID(payload["sid"]),
            token_id=UUID(payload["jti"]), token_type=expected_type,
            issued_at=datetime.fromtimestamp(payload["iat"], UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], UTC),
        )
    except (ValueError, TypeError, AttributeError, OverflowError, OSError) as error:
        raise jwt.InvalidTokenError("Invalid token claims") from error


def hash_refresh_token(token: str) -> str:
    """Digest of an already high-entropy signed token; never store its plaintext."""
    return sha256(token.encode("utf-8")).hexdigest()


# TODO verify_password: dùng _password_hasher.verify_and_update(password, stored_hash);
# xử lý hash NULL/không nhận diện như xác thực thất bại, không lộ hash trong lỗi.
# Nếu thư viện trả updated_hash sau xác thực thành công, cập nhật User.password_hash
# cùng transaction đăng nhập; không hash lại rồi so chuỗi vì mỗi hash có salt riêng.
def verify_password(
        plain_password: str,
        hashed_password: str | None
) -> tuple[bool, str | None]:
    if not isinstance(plain_password, str) or not isinstance(hashed_password, (str, type(None))) or not plain_password or not hashed_password:
        return False, None
    try:
        return _password_hasher.verify_and_update(plain_password, hashed_password)
    except UnknownHashError:
        return False, None


    
# TODO login/register routes: xác thực mật khẩu trước khi issue_login_tokens;
# không cấp token chỉ vì client biết user_id; trả response qua schema có allowlist.
# TODO reset_password/logout_all: revoke tất cả AuthSession của user cùng thay đổi
# mật khẩu; cleanup session hết hạn; không cache role trong JWT để quyết định quyền.
# TODO password_policy: chốt độ dài/giới hạn input ở request schema; benchmark
# chi phí hash với tài nguyên deploy; dùng worker phù hợp nếu endpoint là async.
