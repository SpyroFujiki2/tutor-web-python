"""Model: booking. Mẫu: đọc booking thuộc customer hoặc tutor hiện tại."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Booking
from app.modules.users.user import get_active_user


def get_booking_for_participant(session: Session, booking_id: UUID, user_id: UUID) -> Booking:
    """Mẫu chỉ cho hai bên booking; quyền admin tranh chấp là luồng riêng."""
    get_active_user(session, user_id)
    booking = session.scalar(select(Booking).where(
        Booking.id == booking_id,
        or_(Booking.customer_id == user_id, Booking.tutor_id == user_id),
    ))
    if booking is None:
        raise LookupError("Booking not found or access denied")
    return booking


# TODO create_booking: kiểm tra gói active và customer; tạo Booking cùng ít nhất
# một BookingSession trong một transaction, cấp UUID và trạng thái tường minh.
# TODO confirm_payment: khóa ví/booking, ghi transaction, tạo subscription loại
# booking đúng chủ; gắn subscription_id duy nhất và snapshot giá từ DB.
# TODO assign_tutor/change_status: chốt ma trận trạng thái, quyền và điều kiện
# từng bước; kiểm tra tutor, xung đột lịch; khóa booking trước khi chuyển trạng thái.
# TODO complete/cancel: phối hợp session, subscription, dispute và settlement;
# không đổi booking.status riêng lẻ khi còn cập nhật liên bảng chưa hoàn tất.
