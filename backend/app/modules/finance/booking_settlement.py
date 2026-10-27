"""Model: booking_settlements. Mẫu: gia sư xem quyết toán trả vào ví của mình."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingSettlement, Wallet
from app.models.enums import WalletType
from app.modules.users.user import get_active_user


def get_my_booking_settlement(
    session: Session, booking_id: UUID, tutor_id: UUID,
) -> BookingSettlement:
    get_active_user(session, tutor_id)
    settlement = session.scalar(
        select(BookingSettlement)
        .join(Booking, Booking.id == BookingSettlement.booking_id)
        .join(Wallet, Wallet.id == BookingSettlement.tutor_wallet_id)
        .where(
            Booking.id == booking_id, Booking.tutor_id == tutor_id,
            Wallet.user_id == tutor_id, Wallet.type == WalletType.COMMERCIAL,
        )
    )
    if settlement is None:
        raise LookupError("Settlement not found or access denied")
    return settlement


# TODO settle: khóa booking và ví commercial của tutor được gán; kiểm tra hoàn
# thành/không có tranh chấp chặn; snapshot commission và phân bổ số tiền đúng check.
# TODO allocation_policy: chốt quy tắc làm tròn, phần khả dụng/tạm giữ, thời gian
# release và ví đối ứng nền tảng; chưa tự đặt công thức khi chưa có yêu cầu.
# TODO release_job: khóa settlement held đến hạn; đổi held->released, chuyển
# holding sang available, ghi ledger và actual_released_at nguyên tử/chống chạy lặp.
# TODO refund: khóa settlement/ví; chốt cách thu hồi khi đã release hoặc phát sinh
# debt; ghi giao dịch bù thay vì sửa snapshot phân bổ ban đầu.
