"""Model: lessons. Mẫu: lấy nội dung bài học khi quyền đã mua còn hiệu lực."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Lesson, UserSubscription
from app.models.enums import SubscriptionStatus
from app.modules.learning.course_progress import get_my_course_progress


def list_my_course_lessons(session: Session, subscription_id: UUID, user_id: UUID) -> list[Lesson]:
    progress = get_my_course_progress(session, subscription_id, user_id)
    subscription = session.get(UserSubscription, subscription_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    if (
        subscription is None
        or subscription.status != SubscriptionStatus.ACTIVE
        or subscription.activated_at > now
        or (subscription.expired_at is not None and subscription.expired_at <= now)
    ):
        raise PermissionError("Course subscription is not currently active")
    # Course hidden chỉ ẩn danh mục; không thu hồi quyền của người đã mua.
    return list(session.scalars(
        select(Lesson).where(Lesson.course_id == progress.course_id).order_by(Lesson.order_idx)
    ))


# TODO create/reorder: quyền quản lý khóa; khóa course khi đánh lại order_idx;
# xử lý Unique(course_id, order_idx), không bỏ qua cạnh tranh khi sắp thứ tự.
# TODO update_media: storage có kiểm soát, signed URL sau kiểm tra quyền;
# không trả media_url/assignment_url bằng endpoint danh mục công khai.
# TODO remove: đánh giá dữ liệu attendance đang tham chiếu; không cascade xóa
# lịch sử học. Chốt chính sách phiên bản lesson trước khi hỗ trợ xóa đã xuất bản.
