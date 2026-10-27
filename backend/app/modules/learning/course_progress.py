"""Model: course_progress. Mẫu: chủ subscription xem tiến độ, kể cả lịch sử hết hạn."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CourseProgress, UserSubscription
from app.models.enums import ServiceType
from app.modules.users.user import get_active_user


def get_my_course_progress(session: Session, subscription_id: UUID, user_id: UUID) -> CourseProgress:
    get_active_user(session, user_id)
    progress = session.scalar(
        select(CourseProgress)
        .join(UserSubscription, UserSubscription.id == CourseProgress.subscription_id)
        .where(
            CourseProgress.subscription_id == subscription_id,
            UserSubscription.user_id == user_id,
            UserSubscription.type == ServiceType.COURSE,
        )
    )
    if progress is None:
        raise LookupError("Course progress not found or access denied")
    return progress


# TODO initialize: mỗi lần mua tạo subscription mới và progress riêng; kiểm tra
# type=course/chủ sở hữu, đặt progress=0 và updated_at, chưa có kết quả hoàn thành.
# TODO recalculate: tính từ attendance theo chính sách Live/VOD được chốt;
# dùng Decimal; không tự gộp attendance_ratio thành progress_percent.
# TODO finish: khóa progress; khi đạt 100 cập nhật final_score, result, completed_at
# trong CÙNG UPDATE/transaction để thỏa CheckConstraint; chưa tự đặt công thức điểm.
# TODO history/admin_grading: quyền chấm điểm riêng; log thay đổi và không cho
# client ghi trực tiếp progress_percent hoặc điểm tổng kết.
