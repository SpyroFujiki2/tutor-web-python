"""Owner-scoped bank methods, canonical account numbers and withdrawal guards."""

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashOrder, PaymentMethod
from app.models.enums import CashOrderStatus, CashOrderType
from app.modules.common import actor, add, get, require


def list_my_payment_methods(session: Session, user_id: UUID, *, limit: int = 50, offset: int = 0) -> list[PaymentMethod]:
    require(1 <= limit <= 100 and offset >= 0, 'Phân trang không hợp lệ')
    actor(session, user_id)
    statement = select(PaymentMethod).where(PaymentMethod.user_id == user_id).order_by(PaymentMethod.id).offset(offset).limit(limit)
    return list(session.scalars(statement))


# TODO add_payment_method: lấy user_id từ current_user; chuẩn hóa bank/account;
# thêm UUID và xử lý trùng (user_id, account_number) qua UniqueConstraint.
# TODO update/remove: SELECT theo cả id và user_id; xác định có đơn rút đang dùng
# thông tin này trước khi sửa/xóa; snapshot bank_info trong CashOrder không đổi.
# TODO response schema: chỉ trả trường được phép, che số tài khoản trong danh sách;
# bổ sung phân trang nếu nghiệp vụ cho phép lưu nhiều tài khoản.


def save_payment_method(session: Session, user_id: UUID, values: dict, method_id: UUID | None=None) -> PaymentMethod:
    actor(session, user_id, lock=True)
    require(set(values) == {'bank_name', 'account_number', 'account_holder_name'}, 'Thông tin ngân hàng không hợp lệ')
    values = {key: ' '.join(value.split()) for key, value in values.items()}
    values['account_number'] = normalize_account_number(values['account_number'])
    require(bool(re.fullmatch(r'[A-Z0-9]{4,40}', values['account_number'])), 'Số tài khoản không hợp lệ')
    require(all(0 < len(value) <= 200 for value in values.values()), 'Thông tin ngân hàng không hợp lệ')
    methods = list(session.scalars(select(PaymentMethod).where(PaymentMethod.user_id == user_id)))
    require(not any(row.id != method_id and normalize_account_number(row.account_number or '') == values['account_number']
                    for row in methods), 'Số tài khoản đã được lưu')
    if method_id is None:
        require(len(methods) < 20, 'Mỗi tài khoản được lưu tối đa 20 phương thức thanh toán')
        return add(session, PaymentMethod, user_id=user_id, **values)
    method = get(session, PaymentMethod, method_id, lock=True)
    require(method.user_id == user_id, "Không tìm thấy tài khoản ngân hàng", LookupError)
    require(not used_by_pending_withdrawal(session, user_id, method_id), 'Tài khoản đang có đơn rút chờ xử lý')
    for key in ("bank_name", "account_number", "account_holder_name"):
        setattr(method, key, values[key])
    return method


def remove_payment_method(session: Session, user_id: UUID, method_id: UUID) -> None:
    actor(session, user_id, lock=True)
    method = get(session, PaymentMethod, method_id, lock=True)
    require(method.user_id == user_id, "Không tìm thấy tài khoản ngân hàng", LookupError)
    require(not used_by_pending_withdrawal(session, user_id, method_id),
            "Tài khoản đang được dùng trong đơn rút chờ xử lý")
    session.delete(method)


def normalize_account_number(value: str) -> str:
    return re.sub(r'[ -]', '', value.strip()).upper()


def used_by_pending_withdrawal(session: Session, user_id: UUID, method_id: UUID) -> bool:
    pending = session.scalars(select(CashOrder).where(CashOrder.user_id == user_id,
        CashOrder.order_type == CashOrderType.OUT, CashOrder.status == CashOrderStatus.PENDING))
    return any(isinstance(order.bank_info, dict) and order.bank_info.get('payment_method_id') == str(method_id) for order in pending)
