"""Model: payment_method. Mẫu: danh sách tài khoản ngân hàng của chính user."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PaymentMethod
from app.modules.users.user import get_active_user


def list_my_payment_methods(session: Session, user_id: UUID) -> list[PaymentMethod]:
    get_active_user(session, user_id)
    statement = select(PaymentMethod).where(PaymentMethod.user_id == user_id).order_by(PaymentMethod.id)
    return list(session.scalars(statement))


# TODO add_payment_method: lấy user_id từ current_user; chuẩn hóa bank/account;
# thêm UUID và xử lý trùng (user_id, account_number) qua UniqueConstraint.
# TODO update/remove: SELECT theo cả id và user_id; xác định có đơn rút đang dùng
# thông tin này trước khi sửa/xóa; snapshot bank_info trong CashOrder không đổi.
# TODO response schema: chỉ trả trường được phép, che số tài khoản trong danh sách;
# bổ sung phân trang nếu nghiệp vụ cho phép lưu nhiều tài khoản.
