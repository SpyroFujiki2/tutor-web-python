"""Model: cash_order. Mẫu: chủ đơn xem một yêu cầu nạp/rút của mình."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashOrder
from app.modules.users.user import get_active_user


def get_my_cash_order(session: Session, order_id: UUID, user_id: UUID) -> CashOrder:
    get_active_user(session, user_id)
    order = session.scalar(select(CashOrder).where(
        CashOrder.id == order_id, CashOrder.user_id == user_id,
    ))
    if order is None:
        raise LookupError("Cash order not found or access denied")
    return order


# TODO create_deposit: kiểm tra credit_package active và ví đúng chủ; snapshot
# amount_vnd/credit_amount từ DB; tạo pending và khóa idempotency đã thiết kế.
# TODO create_withdrawal: ví đúng chủ, đủ số dư và chính sách phí; snapshot bank_info
# từ payment_method đã kiểm tra; chốt cách giữ tiền khi đang pending để tránh chi lặp.
# TODO confirm/fail: khóa order/ví; chỉ chuyển pending một lần; external_transaction,
# cập nhật ví và trạng thái đơn cùng transaction, không tin redirect frontend.
# TODO output: dùng schema che bank_info theo vai trò; admin duyệt cần quyền riêng
# và audit log; không cho client gán status=success.
