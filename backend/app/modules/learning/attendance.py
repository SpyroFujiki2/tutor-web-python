"""Model: attendance. Mẫu: xem lịch sử học thuộc một lần đăng ký của chính user."""

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Attendance, Lesson
from app.modules.learning.course_progress import get_my_course_progress


def list_my_attendance(session: Session, subscription_id: UUID, user_id: UUID) -> list[Attendance]:
    get_my_course_progress(session, subscription_id, user_id)
    return list(session.scalars(
        select(Attendance)
        .join(Lesson, and_(Attendance.lesson_id == Lesson.id, Attendance.course_id == Lesson.course_id))
        .where(Attendance.subscription_id == subscription_id)
        .order_by(Lesson.order_idx)
    ))


# TODO record_watch/attendance: kiểm tra subscription còn hạn và đúng khóa;
# lấy course_id từ progress/lesson, không tin course_id client tự chọn.
# TODO concurrent_upsert: dùng PK(subscription_id, lesson_id), khóa/upsert phù hợp;
# duration_watched không âm, không cộng lặp heartbeat; chốt đơn vị và giới hạn.
# TODO recalculate_progress: ghi attendance và cập nhật progress trong một
# transaction; dữ liệu client chỉ là tín hiệu, không tự quyết định điểm/hoàn thành.
