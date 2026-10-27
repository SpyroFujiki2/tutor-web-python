"""Model: booking_sessions. Mẫu: đọc lịch học theo booking được phép xem."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BookingSession
from app.modules.tutoring.booking import get_booking_for_participant


def list_booking_sessions(session: Session, booking_id: UUID, user_id: UUID) -> list[BookingSession]:
    get_booking_for_participant(session, booking_id, user_id)
    return list(session.scalars(
        select(BookingSession).where(BookingSession.booking_id == booking_id)
        .order_by(BookingSession.session_no)
    ))


# TODO schedule: kiểm tra quyền, khóa booking/tutor theo thứ tự thống nhất; kiểm tra
# session_no > 0, thời gian đủ cặp và ends_at > starts_at; tìm lịch giao nhau.
# TODO add/cancel_session: giữ ít nhất một buổi hợp lệ theo chính sách đã chốt;
# Unique(booking_id, session_no) là lớp bảo vệ khi tạo đồng thời.
# TODO complete_session: cập nhật updated_at tường minh; chỉ hoàn tất booking khi
# đủ điều kiện tất cả buổi và không còn tranh chấp chặn quyết toán.
