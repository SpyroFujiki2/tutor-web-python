"""Shared domain rules. Services flush; the API owns commit/rollback."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models import User
from app.models.enums import UserRole, UserStatus

MAX_CREDITS = 2_147_483_647  # Ledger columns in the supplied schema are int32.
ADMIN_ROLES = {UserRole.ADMIN, UserRole.HEAD_ADMIN}


class RateLimitError(ValueError):
    """A domain rate limit shared across workers through database state."""


def now():
    return datetime.now(UTC).replace(tzinfo=None)


def require(condition, message, error=ValueError):
    if not condition:
        raise error(message)


def get(session, model, identity, *, lock=False):
    if lock:
        key = next(iter(model.__table__.primary_key.columns))
        row = session.scalar(select(model).where(key == identity).with_for_update().execution_options(populate_existing=True))
    else:
        row = session.get(model, identity)
    require(row is not None, "Không tìm thấy dữ liệu", LookupError)
    return row


def actor(session, user_id, *, admin=False, lock=False):
    user = get(session, User, user_id, lock=lock)
    require(user.status == UserStatus.ACTIVE, "Tài khoản không hoạt động", PermissionError)
    if admin:
        require(user.role in ADMIN_ROLES, "Cần quyền quản trị", PermissionError)
    return user


def add(session, model, **values):
    if "id" in model.__table__.columns and "id" not in values and model.__table__.c.id.type.python_type is UUID:
        values["id"] = uuid4()
    row = model(**values)
    session.add(row)
    session.flush()
    return row


def audit(session, user, row, action, *, before=None, after=None, reason="Thao tác quản trị"):
    from app.modules.users.action_log import record_admin_action
    return record_admin_action(
        session, admin_id=user.id, target_type=row.__tablename__,
        target_id=getattr(row, "id", getattr(row, "subscription_id", None)), action_code=action,
        old_value=before, new_value=after, reason=reason,
        target_user_id=row.id if isinstance(row, User) else getattr(row, "user_id", None),
    )


def money(value):
    require(type(value) is int and 0 <= value <= MAX_CREDITS, "Số tiền vượt giới hạn cho phép")
    return value
