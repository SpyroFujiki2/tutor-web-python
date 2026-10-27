"""Model: users. Mẫu: lấy tài khoản đang được phép hoạt động."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import UserStatus


def get_active_user(session: Session, user_id: UUID) -> User:
    """user_id phải lấy từ danh tính đã xác thực, không tin ID do client tự chọn."""
    user = session.get(User, user_id)
    if user is None:
        raise LookupError("User not found")
    if user.status != UserStatus.ACTIVE:
        raise PermissionError("User is not active")
    return user


# TODO register_user: chuẩn hóa email, gọi app.core.security.hash_password;
# tạo User với UUID/role/status tường minh; bắt unique email tại biên transaction.
# TODO authenticate_user: hoàn thiện verify trong core/security.py, kiểm tra status,
# giới hạn thử sai, sau đó gọi modules.auth.login.issue_login_tokens; cơ chế đã
# chọn là JWT Bearer có refresh rotation, không trả password_hash hoặc ghi vào log.
# TODO update_profile/change_status: giới hạn trường được sửa; kiểm tra quyền
# admin, khóa user khi đổi trạng thái và ghi ActionLog trong cùng transaction.
