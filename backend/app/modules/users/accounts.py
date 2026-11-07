"""Registration, account maintenance and bank details."""

from datetime import UTC, datetime

from sqlalchemy import select, update

from app.core.security import hash_password, verify_password
from app.models import AuthSession, User
from app.models.enums import UserRole, UserStatus, WalletType
from app.modules.common import actor, add, audit, get, now, require
from app.modules.finance.wallet import create_wallet
from app.modules.users.payment_method import remove_payment_method, save_payment_method

__all__ = ['register_user', 'create_wallet', 'revoke_all', 'change_email', 'list_sessions', 'revoke_session',
           'change_password', 'change_status', 'save_payment_method', 'remove_payment_method']


def register_user(session, email, password, full_name=None):
    email = str(email).strip().lower()
    require(not session.scalar(select(User.id).where(User.email == email)), "Email đã được đăng ký")
    require(8 <= len(password) <= 1024, "Mật khẩu cần từ 8 đến 1024 ký tự")
    user = add(session, User, email=email, password_hash=hash_password(password),
               full_name=full_name.strip() if full_name else None,
               role=UserRole.MEMBER, status=UserStatus.ACTIVE, created_at=now())
    create_wallet(session, user.id, WalletType.NORMAL)
    return user


def revoke_all(session, user_id):
    get(session, User, user_id, lock=True)
    session.execute(update(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
    ).values(revoked_at=datetime.now(UTC)))


def change_email(session, user_id, password, email):
    user = actor(session, user_id, lock=True)
    require(verify_password(password, user.password_hash)[0], "Mật khẩu hiện tại không đúng", PermissionError)
    email = str(email).strip().lower()
    require(not session.scalar(select(User.id).where(User.email == email, User.id != user.id)),
            "Email đã được đăng ký")
    user.email = email
    revoke_all(session, user_id)
    session.flush()
    return user


def list_sessions(session, user_id):
    actor(session, user_id)
    return list(session.scalars(select(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > datetime.now(UTC),
    ).order_by(AuthSession.created_at.desc(), AuthSession.id)))


def revoke_session(session, user_id, session_id):
    actor(session, user_id, lock=True)
    record = get(session, AuthSession, session_id, lock=True)
    require(record.user_id == user_id, "Không tìm thấy phiên đăng nhập", LookupError)
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
    session.flush()


def change_password(session, user_id, old_password, new_password):
    user = actor(session, user_id, lock=True)
    require(verify_password(old_password, user.password_hash)[0], "Mật khẩu hiện tại không đúng", PermissionError)
    require(8 <= len(new_password) <= 1024, "Mật khẩu cần từ 8 đến 1024 ký tự")
    user.password_hash = hash_password(new_password)
    revoke_all(session, user_id)


def change_status(session, admin_id, user_id, status, reason):
    admin = actor(session, admin_id, admin=True)
    user = get(session, User, user_id, lock=True)
    require(user.id != admin.id, "Không thể tự khóa tài khoản")
    require(user.role != UserRole.HEAD_ADMIN and (
        user.role != UserRole.ADMIN or admin.role == UserRole.HEAD_ADMIN),
        "Không đủ quyền thay đổi tài khoản này", PermissionError)
    before = {"status": user.status}
    user.status = status
    if status != UserStatus.ACTIVE:
        revoke_all(session, user_id)
    audit(session, admin, user, "user.status", before=before, after={"status": status}, reason=reason)
    return user


