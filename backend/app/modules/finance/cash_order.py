"""Manual cash orders, bank snapshots and idempotent confirmation/cancellation."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CashOrder, CreditPackage, PaymentMethod, Wallet
from app.models.enums import CashOrderStatus, CashOrderType, UserRole, WalletType
from app.modules.common import actor, add, audit, get, money, now, require
from app.modules.finance.wallet import lock_wallets, owned_wallet, reserved_withdrawals


def get_my_cash_order(session: Session, order_id: UUID, user_id: UUID) -> CashOrder:
    actor(session, user_id)
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


def cash_order_metadata(order: CashOrder) -> dict:
    require(order.bank_info is None or isinstance(order.bank_info, dict), 'Metadata đơn không hợp lệ, cần đối soát')
    return order.bank_info or {}


def create_deposit(session: Session, user_id: UUID, request_id: UUID, package_id: UUID) -> CashOrder:
    actor(session, user_id, lock=True)
    existing = session.get(CashOrder, request_id)
    if existing:
        cash_order_metadata(existing)
        require(existing.user_id == user_id and existing.order_type == CashOrderType.IN
                and existing.package_id == package_id, "Mã yêu cầu đã được dùng")
        return existing
    package = get(session, CreditPackage, package_id, lock=True)
    require(package.is_active and package.credits and package.price, "Gói nạp không hoạt động")
    wallet = owned_wallet(session, user_id)
    return add(session, CashOrder, id=request_id, user_id=user_id, wallet_id=wallet.id,
               order_type=CashOrderType.IN, package_id=package.id,
               amount_vnd=money(package.price), credit_amount=money(package.credits),
               status=CashOrderStatus.PENDING, created_at=now(), updated_at=now())


def create_withdrawal(session: Session, user_id: UUID, request_id: UUID, wallet_type: WalletType, method_id: UUID, amount: int) -> CashOrder:
    actor(session, user_id, lock=True)
    existing = session.get(CashOrder, request_id)
    if existing:
        require(existing.user_id == user_id and existing.order_type == CashOrderType.OUT
                and existing.credit_amount == amount
                and cash_order_metadata(existing).get("payment_method_id") == str(method_id)
                and get(session, Wallet, existing.wallet_id).type == wallet_type, "Mã yêu cầu đã được dùng")
        return existing
    money(amount)
    require(amount > 0, "Số tiền phải dương")
    method = get(session, PaymentMethod, method_id)
    require(method.user_id == user_id, "Không tìm thấy tài khoản ngân hàng", LookupError)
    require(method.bank_name and method.account_number and method.account_holder_name, 'Tài khoản ngân hàng chưa đầy đủ')
    wallet = owned_wallet(session, user_id, wallet_type)
    wallet = lock_wallets(session, wallet.id)[wallet.id]
    require(wallet.debt == 0, "Cần thanh toán công nợ trước khi rút")
    require(wallet.available_balance >= amount, "Số dư không đủ")
    # Debit only on confirmation. All outgoing spends also reserve pending withdrawals.
    pending = reserved_withdrawals(session, wallet)
    require(wallet.available_balance - pending >= amount, "Số dư khả dụng đã được giữ cho đơn rút")
    return add(session, CashOrder, id=request_id, user_id=user_id, wallet_id=wallet.id,
               order_type=CashOrderType.OUT, amount_vnd=amount, credit_amount=amount,
               bank_info={"payment_method_id": str(method_id), "bank_name": method.bank_name,
                          "account_number": method.account_number, "account_holder_name": method.account_holder_name},
               status=CashOrderStatus.PENDING, created_at=now(), updated_at=now())


def decide_cash_order(session: Session, admin_id: UUID, order_id: UUID, success: bool, reason: str) -> CashOrder:
    require(type(success) is bool and 0 < len(reason.strip()) <= 200, 'Kết quả/lý do không hợp lệ')
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, "Cần quản trị cấp cao xác nhận tiền", PermissionError)
    order = get(session, CashOrder, order_id, lock=True)
    require(cash_order_metadata(order).get('provider') in {None, 'manual'},
            'Đơn VNPAY được xác nhận qua IPN; không xác nhận thủ công')
    target = CashOrderStatus.SUCCESS if success else CashOrderStatus.FAILED
    if order.status != CashOrderStatus.PENDING:
        require(order.status == target, "Đơn đã được xử lý với kết quả khác")
        return order
    if success:
        log = audit(session, admin, order, "cash.confirm", after={"status": target}, reason=reason)
        from app.modules.finance.external_transaction import record_manual_movement
        record_manual_movement(session, order, admin.id, log.id)
    else:
        lock_wallets(session, order.wallet_id, require_active=False)
        audit(session, admin, order, "cash.fail", after={"status": target}, reason=reason)
    order.status, order.updated_at = target, now()
    session.flush()
    return order


def cancel_cash_order(session: Session, user_id: UUID, order_id: UUID) -> CashOrder:
    actor(session, user_id)
    order = get(session, CashOrder, order_id, lock=True)
    require(order.user_id == user_id, 'Không tìm thấy đơn thanh toán', LookupError)
    metadata = cash_order_metadata(order)
    require(metadata.get('provider') in {None, 'manual'}, 'Hủy đơn nhà cung cấp đang tạm gác')
    if order.status == CashOrderStatus.FAILED and metadata.get('cancelled_by_user'):
        return order
    require(order.status == CashOrderStatus.PENDING, 'Chỉ hủy được đơn đang chờ')
    lock_wallets(session, order.wallet_id, require_active=False)
    order.status, order.updated_at = CashOrderStatus.FAILED, now()
    order.bank_info = {**metadata, 'cancelled_by_user': True}
    from app.models import ActionLog
    add(session, ActionLog, target_user_id=user_id, target_type='cash_order', target_id=order.id,
        action_code='cash.cancel', reason='Owner cancelled pending manual order',
        old_value={'status': CashOrderStatus.PENDING}, new_value={'status': CashOrderStatus.FAILED}, created_at=now())
    return order
