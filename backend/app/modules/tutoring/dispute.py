"""Model: disputes. Mẫu: customer/tutor xem tranh chấp của booking của mình."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dispute
from app.modules.tutoring.booking import get_booking_for_participant


def get_booking_dispute(session: Session, booking_id: UUID, user_id: UUID) -> Dispute | None:
    get_booking_for_participant(session, booking_id, user_id)
    return session.scalar(select(Dispute).where(Dispute.booking_id == booking_id))


# TODO raise_dispute: kiểm tra người mở thuộc booking và trạng thái cho phép;
# khóa booking, tạo duy nhất một Dispute, đổi booking.status trong cùng transaction.
# TODO assign_admin: xác thực vai trò/phạm vi phân công; quyền đọc booking/messages
# của admin phải dựa trên dispute được giao, không chỉ role=admin.
# TODO resolve: chốt verdict và số tiền hoàn khi partial, khóa booking/settlement/ví;
# tạo giao dịch bù, cập nhật subscription/quyết toán, resolve_at và ActionLog nguyên tử.
# TODO retry: xác định idempotency trước khi nối luồng hoàn tiền thật.
