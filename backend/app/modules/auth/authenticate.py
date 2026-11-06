# TODO authenticate_user: query email đã chuẩn hóa; kiểm tra hash và User.status;
# lỗi đăng nhập thống nhất, dùng dummy hash khi không có user để giảm chênh lệch
# thời gian; rate limit ở biên API. Không log mật khẩu, hash hoặc token.
# JWT Bearer đã được chọn. Xem api/dependencies/auth.py để đọc Authorization;
# modules/auth kiểm tra session/user ở DB, renew có rotation và revoke khi reuse.

from secrets import token_urlsafe
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.models.enums import UserStatus
from app.modules.common import now

dummy_hash = hash_password(token_urlsafe(32))

def authenticate_user(
        session: Session,
        email: str,
        password: str
) -> UUID | None:
    """Return user_id if credentials are valid, else None."""
    normalized_email = email.strip().lower()

    user = session.scalar(select(User).where(User.email == normalized_email).with_for_update())

    stored_hash = user.password_hash if user is not None and user.password_hash else dummy_hash
    valid, updated_hash = verify_password(password, stored_hash)

    if user is None or not valid or user.status != UserStatus.ACTIVE:
        return None

    if updated_hash is not None:
        user.password_hash = updated_hash

    user.last_active_at = now()

    return user.id
