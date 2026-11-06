"""Tutor escrow, release, debt recovery and authorized post-release refunds."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActionLog,
    Booking,
    BookingSession,
    BookingSettlement,
    CashOrder,
    Dispute,
    User,
    UserSubscription,
    Wallet,
)
from app.models.enums import (
    BookingSessionStatus,
    BookingStatus,
    CashOrderStatus,
    CashOrderType,
    EscrowStatus,
    ServiceType,
    SubscriptionStatus,
    TransactionType,
    UserRole,
    WalletType,
)
from app.modules.common import ADMIN_ROLES, actor, add, audit, get, money, now, require
from app.modules.finance.internal_transaction import transfer
from app.modules.finance.wallet import lock_wallets, owned_wallet, platform_wallet, spendable
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


def release_settlement(session: Session, admin_id: UUID, settlement_id: UUID) -> BookingSettlement:
    admin = actor(session, admin_id, admin=True)
    initial = get(session, BookingSettlement, settlement_id)
    booking = get(session, Booking, initial.booking_id, lock=True)
    settlement = get(session, BookingSettlement, settlement_id, lock=True)
    if settlement.status == EscrowStatus.RELEASED:
        return settlement
    require(settlement.status == EscrowStatus.HELD and booking.status == BookingStatus.COMPLETED,
            "Quyết toán đang tranh chấp hoặc đã đóng")
    require(settlement.release_date is not None and settlement.release_date <= now(), "Chưa đến hạn giải ngân")
    platform_id = platform_wallet(session)
    wallets = lock_wallets(session, platform_id, settlement.tutor_wallet_id)
    wallet = wallets[settlement.tutor_wallet_id]
    require(wallet.holding_balance >= settlement.hold_amount, "Số dư tạm giữ không khớp")
    wallet.holding_balance -= settlement.hold_amount
    wallet.updated_at = now()
    settlement.status, settlement.actual_released_at = EscrowStatus.RELEASED, now()
    # Flush releases this settlement's reservation before moving its funds.
    session.flush()
    pay_tutor_income(session, wallet, settlement.hold_amount, booking.subscription_id, admin.id)
    audit(session, admin, settlement, "settlement.release", after={'status': settlement.status})
    return settlement


def settle_booking(session: Session, user_id: UUID, booking_id: UUID) -> BookingSettlement:
    user = actor(session, user_id)
    booking = get(session, Booking, booking_id, lock=True)
    require(booking.customer_id == user_id or user.role in ADMIN_ROLES, 'Không được quyết toán đơn này', PermissionError)
    require(booking.status in {BookingStatus.ASSIGNED, BookingStatus.COMPLETED}, 'Đơn chưa đủ điều kiện quyết toán')
    existing = session.scalar(select(BookingSettlement).where(BookingSettlement.booking_id == booking.id))
    if existing:
        require(existing.status != EscrowStatus.REFUNDED, 'Quyết toán đã hoàn tiền')
        return existing
    sessions = list(session.scalars(select(BookingSession).where(BookingSession.booking_id == booking.id,
        BookingSession.status != BookingSessionStatus.CANCELLED)))
    require(sessions and all(row.status == BookingSessionStatus.COMPLETED for row in sessions), 'Chưa hoàn tất các buổi học')
    require(not session.scalar(select(Dispute.id).where(Dispute.booking_id == booking.id, Dispute.is_completed.is_(False))),
            'Đơn đang có tranh chấp')
    subscription = get(session, UserSubscription, booking.subscription_id, lock=True)
    require(subscription.type == ServiceType.BOOKING and subscription.user_id == booking.customer_id
            and subscription.status == SubscriptionStatus.ACTIVE, 'Quyền mua không khớp booking')
    total = money(subscription.price_at_purchase)
    wallet = owned_wallet(session, booking.tutor_id, WalletType.COMMERCIAL)
    platform_id = platform_wallet(session)
    wallets = lock_wallets(session, platform_id, wallet.id)
    wallet = wallets[wallet.id]
    require(wallet.commission_rate is not None, 'Chưa cấu hình phí gia sư')
    fee = total * wallet.commission_rate // 100
    income = total - fee
    require(spendable(session, wallets[platform_id]) >= income, 'Ví nền tảng thiếu tiền bảo đảm quyết toán')
    row = add(session, BookingSettlement, booking_id=booking.id, tutor_wallet_id=wallet.id,
        total_amount=total, commission_rate=wallet.commission_rate, platform_fee=fee, tutor_income=income,
        available_amount=0, hold_amount=income, status=EscrowStatus.HELD,
        release_date=now() + timedelta(days=7), created_at=now())
    wallet.holding_balance += income
    wallet.updated_at = now()
    return row


def pay_tutor_income(session: Session, wallet: Wallet, amount: int, subscription_id: UUID, admin_id: UUID | None) -> None:
    """Gross revenue and debt recovery are separate immutable ledger entries."""
    if amount == 0:
        return
    platform_id = platform_wallet(session)
    transfer(session, platform_id, wallet.id, amount, TransactionType.REVENUE,
             subscription_id=subscription_id, admin_id=admin_id, allow_inactive_destination=True)
    recovery = min(wallet.debt, amount)
    if recovery:
        entry = transfer(session, wallet.id, platform_id, recovery, TransactionType.REFUND,
                         subscription_id=subscription_id, admin_id=admin_id,
                         allow_debt_source=True, allow_inactive_source=True)
        wallet.debt -= recovery
        wallet.updated_at = now()
        add(session, ActionLog, admin_id=admin_id, target_user_id=wallet.user_id, target_type='wallets', target_id=wallet.id,
            action_code='wallet.debt_repay', reason='Tutor income set off against debt', created_at=now(),
            new_value={'amount': recovery, 'debt': wallet.debt, 'transaction_id': str(entry.id)})


def refund_released_booking(session: Session, admin_id: UUID, booking_id: UUID, reason: str) -> BookingSettlement:
    """Head-admin full credit refund, with tutor recovery and explicit debt."""
    admin = actor(session, admin_id, admin=True)
    require(admin.role == UserRole.HEAD_ADMIN, 'Cần quản trị cấp cao hoàn sau giải ngân', PermissionError)
    require(0 < len(reason.strip()) <= 200, 'Cần lý do hoàn tiền')
    booking = get(session, Booking, booking_id, lock=True)
    require(admin.id not in {booking.customer_id, booking.tutor_id}, 'Không tự xử lý đơn có liên quan', PermissionError)
    settlement = session.scalar(select(BookingSettlement).where(BookingSettlement.booking_id == booking_id).with_for_update())
    require(settlement is not None, 'Không tìm thấy quyết toán', LookupError)
    if settlement.status == EscrowStatus.REFUNDED and booking.status == BookingStatus.REFUNDED:
        require(session.scalar(select(ActionLog.id).where(ActionLog.target_id == settlement.id,
            ActionLog.action_code == 'settlement.refund_released').limit(1)) is not None,
            'Đơn đã được hoàn qua luồng khác')
        return settlement
    require(settlement.status == EscrowStatus.RELEASED and booking.status == BookingStatus.COMPLETED,
            'Chỉ áp dụng cho booking đã hoàn tất và giải ngân')
    subscription = get(session, UserSubscription, booking.subscription_id, lock=True)
    # Prevent new withdrawal reservations while locking/cancelling the pending ones.
    get(session, User, booking.tutor_id, lock=True)
    pending = list(session.scalars(select(CashOrder).where(CashOrder.wallet_id == settlement.tutor_wallet_id,
        CashOrder.order_type == CashOrderType.OUT, CashOrder.status == CashOrderStatus.PENDING)
        .order_by(CashOrder.id).with_for_update()))
    customer = owned_wallet(session, booking.customer_id, require_active=False)
    platform_id = platform_wallet(session)
    wallets = lock_wallets(session, platform_id, customer.id, settlement.tutor_wallet_id, require_active=False)
    tutor, platform = wallets[settlement.tutor_wallet_id], wallets[platform_id]
    recovered = min(tutor.available_balance, settlement.tutor_income)
    shortfall = settlement.tutor_income - recovered
    money(tutor.debt + shortfall)
    require(spendable(session, platform) + recovered >= settlement.total_amount,
            'Ví nền tảng thiếu thanh khoản để hoàn; cần bổ sung credit trước')
    for order in pending:
        require((order.bank_info or {}).get('provider') != 'vnpay', 'Đơn nhà cung cấp cần xử lý riêng')
        order.status, order.updated_at = CashOrderStatus.FAILED, now()
        order.bank_info = {**(order.bank_info or {}), 'cancelled_for_refund': str(booking.id)}
        audit(session, admin, order, 'cash.fail', after={'status': order.status}, reason=reason)
    session.flush()
    if recovered:
        transfer(session, tutor.id, platform_id, recovered, TransactionType.REFUND,
                 subscription_id=subscription.id, admin_id=admin_id,
                 allow_inactive_source=True, allow_debt_source=True)
    tutor.debt += shortfall
    tutor.updated_at = now()
    transfer(session, platform_id, customer.id, settlement.total_amount, TransactionType.REFUND,
             subscription_id=subscription.id, admin_id=admin_id, allow_inactive_destination=True)
    subscription.status = SubscriptionStatus.CANCELLED
    booking.status, booking.last_updated = BookingStatus.REFUNDED, now()
    settlement.status = EscrowStatus.REFUNDED
    audit(session, admin, tutor, 'wallet.debt', after={'debt': tutor.debt, 'amount': shortfall}, reason=reason)
    audit(session, admin, settlement, 'settlement.refund_released', after={'status': settlement.status,
          'refund_amount': settlement.total_amount, 'recovered_amount': recovered, 'debt': shortfall}, reason=reason)
    return settlement
