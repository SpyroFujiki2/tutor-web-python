"""Model: messages. Mẫu: gửi tin nhắn văn bản trong chat booking thông thường."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Message
from app.modules.tutoring.booking import get_booking_for_participant


def send_booking_message(
    session: Session, *, booking_id: UUID, sender_id: UUID, content: str,
) -> Message:
    """Không commit: message chỉ tồn tại lâu dài khi transaction của caller thành công."""
    get_booking_for_participant(session, booking_id, sender_id)
    content = content.strip()
    if not content:
        raise ValueError("Message content must not be blank")
    message = Message(
        booking_id=booking_id, sender_id=sender_id, dispute_id=None,
        content=content, created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(message)
    session.flush()
    return message


# TODO list_messages: kiểm tra quyền TRƯỚC query; tách dispute_id IS NULL với chat
# tranh chấp; phân trang bằng (created_at, id), không trộn hai phạm vi.
# TODO send_dispute_message: đối chiếu dispute.booking_id, hai bên booking hoặc
# admin được phân công; FK ghép bảo vệ cùng booking nhưng không thay kiểm tra quyền.
# TODO file_message: upload qua storage, kiểm tra quyền/loại/kích thước file;
# dùng key hoặc URL được kiểm soát; không để user tùy ý gán file_url bên thứ ba.
# TODO realtime: publish WebSocket/event SAU commit; chốt chính sách nhắn khi booking
# đã đóng và thêm rate limit trước khi expose endpoint.
