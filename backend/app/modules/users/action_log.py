"""Model: action_logs. Mẫu: ghi một thao tác admin vào transaction hiện tại."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActionLog
from app.models.enums import UserRole
from app.modules.users.user import get_active_user


def record_admin_action(
    session: Session,
    *,
    admin_id: UUID,
    action_code: str,
    target_type: str,
    target_id: UUID,
    reason: str,
    target_user_id: UUID | None = None,
    old_value: dict | None = None,
    new_value: dict | None = None,
) -> ActionLog:
    """Chỉ ghi log; caller vẫn phải kiểm tra quyền thực hiện thao tác được ghi."""
    admin = get_active_user(session, admin_id)
    if admin.role not in {UserRole.ADMIN, UserRole.HEAD_ADMIN}:
        raise PermissionError("Administrator role required")
    if not action_code.strip() or not target_type.strip() or not reason.strip():
        raise ValueError("Action code, target type and reason are required")
    log = ActionLog(
        id=uuid4(), admin_id=admin_id, target_user_id=target_user_id,
        target_type=target_type.strip(), target_id=target_id,
        action_code=action_code.strip(), reason=reason.strip(),
        old_value=safe_snapshot(target_type, old_value),
        new_value=safe_snapshot(target_type, new_value),
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(log)
    session.flush()
    return log


# TODO old_value/new_value: tạo snapshot theo allowlist cho từng action_code;
# loại password_hash, token, dữ liệu ngân hàng nhạy cảm trước khi đưa vào JSONB.
# TODO list_admin_logs: kiểm tra quyền và phân trang theo created_at + id;
# lọc target_user_id/target_id; không cung cấp API sửa hoặc xóa lịch sử.
# TODO integrate: thay đổi nghiệp vụ và ghi log trong cùng session.begin();
# nếu một bước lỗi phải rollback cả hai, không commit riêng trong hàm này.


_SNAPSHOT_FIELDS = {
    "users": {"role", "status", "revoked_sessions"},
    "courses": {"title", "price", "status", "is_live", "lesson_ids"},
    "lessons": {"order_idx", "lesson_ids"},
    "posts": {"is_hidden", "min_role_level"},
    "comments": {"is_hidden"},
    "role_requests": {"role", "status"},
    "comment_report": {"status"},
    "booking": {"status", "tutor_id"},
    "booking_sessions": {"status", "starts_at", "ends_at"},
    "disputes": {"verdict", "refund_amount"},
    "course_progress": {"midterm_score", "endterm_score", "practice_score", "lesson_id", "is_absent"},
    "user_subscriptions": {"status", "amount"},
    "cash_order": {"status"},
    "tutoring_package": {"name", "price", "is_active"},
    "credit_package": {"name", "credits", "price", "is_active"},
    "wallets": {"is_active", "commission_rate", "contract_id", "amount", "debt", "transaction_id"},
    "internal_transaction": {"amount", "transaction_id"},
    "external_transaction": {"amount", "transaction_id"},
    "booking_settlements": {"status", "refund_amount", "debt", "recovered_amount"},
}


def safe_snapshot(target_type: str, values: dict | None) -> dict | None:
    """Only allow documented scalar fields; never copy request bodies or secrets."""
    if values is None:
        return None
    allowed = _SNAPSHOT_FIELDS.get(target_type, set())
    return {key: value for key, value in values.items() if key in allowed
            and (value is None or isinstance(value, (str, int, bool))
                 or (key == "lesson_ids" and isinstance(value, list) and all(isinstance(item, str) for item in value)))}


def list_admin_logs(
    session: Session, admin_id: UUID, *, limit: int = 20, offset: int = 0,
    target_id: UUID | None = None, target_user_id: UUID | None = None,
) -> list[ActionLog]:
    admin = get_active_user(session, admin_id)
    if admin.role not in {UserRole.ADMIN, UserRole.HEAD_ADMIN}:
        raise PermissionError("Administrator role required")
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    statement = select(ActionLog)
    if target_id:
        statement = statement.where(ActionLog.target_id == target_id)
    if target_user_id:
        statement = statement.where(ActionLog.target_user_id == target_user_id)
    return list(session.scalars(statement.order_by(ActionLog.created_at.desc().nulls_last(), ActionLog.id)
                               .offset(offset).limit(limit)))
