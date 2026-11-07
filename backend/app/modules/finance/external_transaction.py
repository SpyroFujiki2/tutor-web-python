"""Manual external credit movements and explicit compensating entries."""

from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from app.models import ActionLog, CashOrder, ExternalTransaction
from app.models.enums import CashOrderType, UserRole, WalletType
from app.modules.common import actor, add, audit, get, money, now, require
from app.modules.finance.wallet import get_my_wallet, lock_wallets, reserved_withdrawals


def list_my_external_transactions(
    session: Session, user_id: UUID, wallet_type: WalletType, *, limit: int = 50, offset: int = 0,
) -> list[RowMapping]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be between 1 and 100")
    wallet = get_my_wallet(session, user_id, wallet_type, include_inactive=True)
    statement = select(
        ExternalTransaction.id, ExternalTransaction.amount,
        ExternalTransaction.cash_order_id, ExternalTransaction.created_at,
    ).where(or_(
        ExternalTransaction.source_wallet_id == wallet.id,
        ExternalTransaction.destination_wallet_id == wallet.id,
    )).order_by(ExternalTransaction.created_at.desc().nulls_last(), ExternalTransaction.id).offset(offset).limit(limit)
    return list(session.execute(statement).mappings())


# TODO deposit_callback: xác thực nhà cung cấp, đối chiếu cash_order, số tiền/đơn vị;
# khóa order/ví, chống callback lặp và chỉ cộng số dư khi xác minh thành công.
# TODO withdrawal: xác thực chủ ví, bank_info snapshot, duyệt/rút theo chính sách;
# tách gọi nhà cung cấp khỏi DB transaction dài, theo dõi retry/reconciliation.
# TODO provider_reference: schema chưa có khóa idempotency/reference nhà cung cấp;
# thiết kế cột/bảng bổ sung và unique trước khi xử lý tiền thật.
# TODO ledger: không chỉnh/xóa giao dịch đã ghi; hoàn/điều chỉnh bằng bản ghi bù.


def external_checksum(identity: UUID, order_id: UUID, amount: int, before: int, after: int) -> str:
    return sha256(f'{identity}:{order_id}:{amount}:{before}:{after}'.encode()).hexdigest()


def record_manual_movement(session: Session, order: CashOrder, admin_id: UUID, log_id: UUID) -> ExternalTransaction:
    """Caller has authorized the head admin and locked this pending manual order."""
    require(order.order_type in {CashOrderType.IN, CashOrderType.OUT}, 'Loại đơn không hợp lệ')
    from app.modules.finance.cash_order import cash_order_metadata
    require(cash_order_metadata(order).get('provider') in {None, 'manual'}, 'Không xử lý đơn nhà cung cấp qua luồng thủ công')
    incoming = order.order_type == CashOrderType.IN
    # An already-received deposit can settle into a frozen wallet; payouts
    # still require an active wallet and the freeze remains in effect.
    wallet = lock_wallets(session, order.wallet_id, require_active=not incoming)[order.wallet_id]
    require(wallet.user_id == order.user_id, 'Ví không thuộc chủ đơn')
    amount, before = money(order.credit_amount), money(wallet.available_balance)
    require(amount > 0 and money(order.amount_vnd) > 0, 'Đơn không có số tiền hợp lệ')
    if not incoming:
        require(wallet.type == WalletType.COMMERCIAL, 'Chỉ ví gia sư được rút tiền')
        require(wallet.debt == 0, 'Ví có công nợ, không thể xác nhận rút')
        pending = reserved_withdrawals(session, wallet)
        require(before >= pending, 'Số dư không đủ cho các đơn rút đã giữ tiền')
    after = money(before + amount if incoming else before - amount)
    wallet.available_balance, wallet.updated_at = after, now()
    identity = uuid4()
    return add(session, ExternalTransaction, id=identity, source_wallet_id=None if incoming else wallet.id,
               destination_wallet_id=wallet.id if incoming else None, amount=amount, cash_order_id=order.id,
               balance_before=before, balance_after=after, created_at=now(), created_by_admin_id=admin_id,
               ref_log_id=log_id, checksum=external_checksum(identity, order.id, amount, before, after))


def reverse_external_transaction(session: Session, admin_id: UUID, transaction_id: UUID,
                                 request_id: UUID, reason: str) -> ExternalTransaction:
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao lập bút toán bù', PermissionError)
    original = get(session, ExternalTransaction, transaction_id, lock=True)
    require(original.cash_order_id is not None, 'Giao dịch không thuộc đơn thủ công')
    order = get(session, CashOrder, original.cash_order_id)
    from app.modules.finance.cash_order import cash_order_metadata
    require(cash_order_metadata(order).get('provider') in {None, 'manual'}, 'Điều chỉnh nhà cung cấp đang tạm gác')
    if original.ref_log_id:
        original_log = get(session, ActionLog, original.ref_log_id)
        require(original_log.action_code != 'external.reverse', 'Không đảo bút toán bù')
    previous = session.scalar(select(ExternalTransaction).join(ActionLog, ActionLog.id == ExternalTransaction.ref_log_id)
        .where(ActionLog.action_code == 'external.reverse', ActionLog.target_id == original.id))
    if previous:
        require(previous.id == request_id, 'Giao dịch đã có bút toán bù')
        return previous
    require(session.get(ExternalTransaction, request_id) is None, 'Mã yêu cầu đã được dùng')
    require(original.checksum == external_checksum(original.id, order.id, original.amount,
            original.balance_before, original.balance_after), 'Checksum giao dịch gốc không hợp lệ')
    require((original.source_wallet_id is None) != (original.destination_wallet_id is None), 'Giao dịch gốc không hợp lệ')
    wallet_id = original.source_wallet_id or original.destination_wallet_id
    wallet = lock_wallets(session, wallet_id, require_active=False)[wallet_id]
    incoming = original.source_wallet_id is not None
    amount, before = money(original.amount), money(wallet.available_balance)
    if not incoming:
        from app.modules.finance.wallet import spendable
        require(wallet.is_active and wallet.debt == 0 and spendable(session, wallet) >= amount,
                'Ví không đủ số dư khả dụng để đảo giao dịch')
    after = money(before + amount if incoming else before - amount)
    log = audit(session, admin, original, 'external.reverse',
                after={'amount': amount, 'transaction_id': str(request_id)}, reason=reason)
    wallet.available_balance, wallet.updated_at = after, now()
    return add(session, ExternalTransaction, id=request_id, source_wallet_id=original.destination_wallet_id,
               destination_wallet_id=original.source_wallet_id, amount=amount, cash_order_id=order.id,
               balance_before=before, balance_after=after, created_by_admin_id=admin_id, ref_log_id=log.id,
               created_at=now(), checksum=external_checksum(request_id, order.id, amount, before, after))
