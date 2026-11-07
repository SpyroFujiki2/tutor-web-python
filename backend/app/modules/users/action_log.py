"""Model: action_logs. Mẫu: ghi một thao tác admin vào transaction hiện tại."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import String, case, cast, or_, select
from sqlalchemy.orm import Session

from app.models import ActionLog, User
from app.models.enums import UserRole
from app.modules.users.user import get_active_user
from app.modules.users.audit_labels import ACTION_LABELS, TARGET_LABELS, REASON_LABELS, ACTION_OPERATIONS, LEGACY_OPERATIONS, OPERATION_LABELS, OPERATION_SEARCH_LABELS, matching_codes, operation_for


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
    operation: str | None = None,
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
        operation=operation_for(action_code, operation),
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
    "course_progress": {"midterm_score", "endterm_score", "practice_score", "lesson_id", "is_absent", "assignment_completed"},
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


def audit_operation_expression():
    save_codes = [code for code in ACTION_OPERATIONS if code.endswith('.save')]
    old_update = case((ActionLog.action_code.in_(save_codes), 'PUT'), else_='PATCH')
    historical_operation = case(*[(ActionLog.action_code == code, verb) for code, verb in ACTION_OPERATIONS.items()], else_='OTHER')
    return case(
        (ActionLog.operation.in_(OPERATION_LABELS), ActionLog.operation),
        (ActionLog.operation == 'SELECT', 'GET'), (ActionLog.operation == 'INSERT', 'POST'),
        (ActionLog.operation == 'UPDATE', old_update), else_=historical_operation,
    )


def list_admin_logs(
    session: Session, admin_id: UUID, *, limit: int = 20, offset: int = 0,
    target_id: UUID | None = None, target_user_id: UUID | None = None,
    q: str | None = None, action_code: str | None = None, target_type: str | None = None,
    actor: str | None = None, actor_kind: str | None = None,
    created_from: datetime | None = None, created_to: datetime | None = None,
    operation: str | None = None,
) -> list[ActionLog]:
    admin = get_active_user(session, admin_id)
    if admin.role not in {UserRole.ADMIN, UserRole.HEAD_ADMIN}:
        raise PermissionError("Administrator role required")
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    statement = select(ActionLog)
    classified_operation = audit_operation_expression()
    if target_id:
        statement = statement.where(ActionLog.target_id == target_id)
    if target_user_id:
        statement = statement.where(ActionLog.target_user_id == target_user_id)
    def pattern(value):
        return '%' + value.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'

    def matching_users(value):
        text = pattern(value)
        conditions = [User.full_name.ilike(text, escape='\\'), User.email.ilike(text, escape='\\'),
                      cast(User.id, String).ilike(text, escape='\\')]
        try:
            conditions.append(User.id == UUID(value.strip()))
        except ValueError:
            pass
        return select(User.id).where(or_(*conditions))

    if q and q.strip():
        text = pattern(q)
        try:
            identity = UUID(q.strip())
        except ValueError:
            identity = None
        statement = statement.where(or_(
            *(column.ilike(text, escape='\\') for column in (ActionLog.reason, ActionLog.action_code, ActionLog.target_type)),
            cast(ActionLog.id, String).ilike(text, escape='\\'), cast(ActionLog.target_id, String).ilike(text, escape='\\'),
            ActionLog.admin_id.in_(matching_users(q)), ActionLog.target_user_id.in_(matching_users(q)),
            ActionLog.action_code.in_(matching_codes(ACTION_LABELS, q)),
            ActionLog.target_type.in_(matching_codes(TARGET_LABELS, q)),
            ActionLog.reason.in_(matching_codes(REASON_LABELS, q)),
            classified_operation.in_(matching_codes(OPERATION_SEARCH_LABELS, q)),
            *(column == identity for column in (ActionLog.id, ActionLog.target_id, ActionLog.admin_id, ActionLog.target_user_id) if identity),
        ))
    if action_code:
        statement = statement.where(ActionLog.action_code == action_code)
    if target_type:
        statement = statement.where(ActionLog.target_type == target_type)
    if operation:
        both_updates = operation == 'UPDATE'
        operation = LEGACY_OPERATIONS.get(operation, operation)
        if operation not in OPERATION_LABELS:
            raise ValueError('Loại thao tác không hợp lệ')
        statement = statement.where(classified_operation.in_(['PUT', 'PATCH']) if both_updates else classified_operation == operation)
    if actor and actor.strip():
        statement = statement.where(ActionLog.admin_id.in_(matching_users(actor)))
    if actor_kind == 'system':
        statement = statement.where(ActionLog.admin_id.is_(None))
    elif actor_kind == 'user':
        statement = statement.where(ActionLog.admin_id.is_not(None))
    start = created_from.astimezone(UTC).replace(tzinfo=None) if created_from and created_from.tzinfo else created_from
    end = created_to.astimezone(UTC).replace(tzinfo=None) if created_to and created_to.tzinfo else created_to
    if start and end and start >= end:
        raise ValueError('Ngày kết thúc phải sau ngày bắt đầu')
    if start:
        statement = statement.where(ActionLog.created_at >= start)
    if end:
        statement = statement.where(ActionLog.created_at < end)
    return list(session.scalars(statement.order_by(ActionLog.created_at.desc().nulls_last(), ActionLog.id)
                               .offset(offset).limit(limit)))
