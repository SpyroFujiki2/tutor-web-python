"""Model: action_logs. Mẫu: ghi một thao tác admin vào transaction hiện tại."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

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
