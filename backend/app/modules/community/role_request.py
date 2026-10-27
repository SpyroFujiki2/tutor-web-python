"""Model: role_requests. Mẫu: xem lịch sử yêu cầu nâng bậc của chính user."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RoleRequest
from app.modules.users.user import get_active_user


def list_my_role_requests(session: Session, user_id: UUID, *, limit: int = 20) -> list[RoleRequest]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    get_active_user(session, user_id)
    return list(session.scalars(
        select(RoleRequest).where(RoleRequest.user_id == user_id)
        .order_by(RoleRequest.created_at.desc().nulls_last(), RoleRequest.id).limit(limit)
    ))


# TODO submit: lấy role hiện tại từ DB vào current_role_at_request; chỉ đề nghị
# bậc kế tiếp guest->member->student->trainee_tutor->tutor->admin->head_admin.
# TODO approve: kiểm tra người được quyền duyệt bậc đó; khóa request và user;
# kiểm tra lại role hiện tại so với snapshot, pending -> approved + đổi role + log.
# TODO reject: lý do/admin_note và thời điểm; không đổi role, không cho xử lý lặp.
# TODO pending_policy: quyết định một hay nhiều request pending, cách chọn bộ câu
# hỏi/priority và bổ sung constraint/index nếu cần; head_admin không có bậc tiếp.
