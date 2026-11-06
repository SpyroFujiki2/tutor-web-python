"""Booking lifecycle: creation, entitlement, tutor assignment and completion."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Booking,
    BookingSession,
    BookingSettlement,
    Dispute,
    TutoringPackage,
    UserSubscription,
)
from app.models.enums import (
    BookingSessionStatus,
    BookingStatus,
    EscrowStatus,
    ServiceType,
    SubscriptionStatus,
    TransactionType,
    UserRole,
    WalletType,
)
from app.modules.common import ADMIN_ROLES, actor, add, audit, get, now, require
from app.modules.finance.payments import lock_wallets, owned_wallet, platform_wallet, transfer
from app.modules.finance.booking_settlement import pay_tutor_income, settle_booking
from app.modules.tutoring.access import accessible_booking
from app.modules.tutoring.booking_session import session_values, check_schedule


def get_booking_for_participant(session: Session, booking_id: UUID, user_id: UUID) -> Booking:
    return accessible_booking(session, user_id, booking_id)


# TODO create_booking: kiểm tra gói active và customer; tạo Booking cùng ít nhất
# một BookingSession trong một transaction, cấp UUID và trạng thái tường minh.
# TODO confirm_payment: khóa ví/booking, ghi transaction, tạo subscription loại
# booking đúng chủ; gắn subscription_id duy nhất và snapshot giá từ DB.
# TODO assign_tutor/change_status: chốt ma trận trạng thái, quyền và điều kiện
# từng bước; kiểm tra tutor, xung đột lịch; khóa booking trước khi chuyển trạng thái.
# TODO complete/cancel: phối hợp session, subscription, dispute và settlement;
# không đổi booking.status riêng lẻ khi còn cập nhật liên bảng chưa hoàn tất.


def create_booking(session: Session, user_id: UUID, values: dict) -> Booking:
    require(1 <= len(values["sessions"]) <= 100, "Đơn phải có 1–100 buổi học")
    actor(session, user_id, lock=True)
    existing = session.get(Booking, values["request_id"])
    if existing:
        require(existing.customer_id == user_id and existing.package_id == values["package_id"]
                and existing.subject == values["subject"] and existing.requirements == values["requirements"],
                "Mã yêu cầu đã được dùng")
        return existing
    package = get(session, TutoringPackage, values["package_id"])
    require(package.is_active and package.price is not None, "Gói gia sư không hoạt động")
    row = add(session, Booking, id=values["request_id"], package_id=package.id, customer_id=user_id,
              subject=values["subject"], requirements=values["requirements"], status=BookingStatus.PENDING,
              created_at=now(), last_updated=now())
    intervals = []
    for index, data in enumerate(values["sessions"], 1):
        data = session_values(data)
        start, end = data.get("starts_at"), data.get("ends_at")
        if start is not None:
            require(start > now(), "Buổi học cần ở tương lai")
            require(not any(start < b and end > a for a, b in intervals), "Các buổi trong đơn trùng lịch")
            intervals.append((start, end))
        add(session, BookingSession, booking_id=row.id, session_no=index, **data,
            status=BookingSessionStatus.SCHEDULED, created_at=now(), updated_at=now())
    return row


def pay_booking(session: Session, user_id: UUID, booking_id: UUID) -> Booking:
    actor(session, user_id, lock=True)
    booking = accessible_booking(session, user_id, booking_id, lock=True)
    require(booking.customer_id == user_id, "Chỉ người mua được thanh toán", PermissionError)
    if booking.subscription_id:
        require(booking.status in {BookingStatus.CONFIRMED, BookingStatus.ASSIGNED, BookingStatus.COMPLETED}, "Đơn đã đóng")
        return booking
    require(booking.status == BookingStatus.PENDING, "Trạng thái không cho thanh toán")
    package = get(session, TutoringPackage, booking.package_id)
    require(package.is_active and package.price is not None, "Gói gia sư không hoạt động")
    subscription = add(session, UserSubscription, user_id=user_id, type=ServiceType.BOOKING,
                       title_at_purchase=package.name, price_at_purchase=package.price,
                       status=SubscriptionStatus.ACTIVE, activated_at=now())
    transfer(session, owned_wallet(session, user_id).id, platform_wallet(session), package.price,
             TransactionType.PAYMENT, subscription_id=subscription.id)
    booking.subscription_id, booking.status, booking.last_updated = subscription.id, BookingStatus.CONFIRMED, now()
    return booking


def assign_tutor(session: Session, admin_id: UUID, booking_id: UUID, tutor_id: UUID) -> Booking:
    admin = actor(session, admin_id, admin=True)
    booking = get(session, Booking, booking_id, lock=True)
    require(booking.status in {BookingStatus.CONFIRMED, BookingStatus.ASSIGNED}, "Đơn chưa thanh toán hoặc đã đóng")
    tutor = actor(session, tutor_id, lock=True)
    require(tutor.role == UserRole.TUTOR and tutor_id != booking.customer_id, "Gia sư không hợp lệ")
    require(not session.scalar(select(BookingSession.id).where(
        BookingSession.booking_id == booking.id, BookingSession.status == BookingSessionStatus.COMPLETED).limit(1)),
        "Không đổi gia sư sau khi đã bắt đầu học")
    owned_wallet(session, tutor_id, WalletType.COMMERCIAL)
    booking.tutor_id = tutor_id
    booking.status = BookingStatus.ASSIGNED
    session.flush()
    for row in session.scalars(select(BookingSession).where(
        BookingSession.booking_id == booking.id, BookingSession.status != BookingSessionStatus.CANCELLED)):
        check_schedule(session, booking, row.starts_at, row.ends_at, exclude=row.id)
    booking.last_updated = now()
    audit(session, admin, booking, "booking.assign", after={"tutor_id": str(tutor_id)})
    return booking


def complete_booking(session: Session, user_id: UUID, booking_id: UUID) -> Booking:
    user = actor(session, user_id)
    booking = accessible_booking(session, user_id, booking_id, lock=True, administration=True)
    require(booking.customer_id == user_id or user.role in ADMIN_ROLES, "Chỉ khách hàng hoặc quản trị được xác nhận", PermissionError)
    if booking.status == BookingStatus.COMPLETED:
        return booking
    require(booking.status == BookingStatus.ASSIGNED, "Đơn không thể hoàn tất")
    sessions = list(session.scalars(select(BookingSession).where(
        BookingSession.booking_id == booking_id, BookingSession.status != BookingSessionStatus.CANCELLED)))
    require(sessions and all(row.status == BookingSessionStatus.COMPLETED for row in sessions), "Chưa hoàn tất các buổi học")
    require(not session.scalar(select(Dispute.id).where(Dispute.booking_id == booking_id, Dispute.is_completed.is_(False))), "Còn tranh chấp")
    settle_booking(session, user_id, booking.id)
    subscription = get(session, UserSubscription, booking.subscription_id, lock=True)
    booking.status, booking.last_updated = BookingStatus.COMPLETED, now()
    subscription.expired_at = now() + timedelta(days=365)
    return booking


def refund_booking(session: Session, booking: Booking, amount: int, *, admin_id: UUID | None=None) -> None:
    from app.modules.common import money
    money(amount)
    subscription = get(session, UserSubscription, booking.subscription_id, lock=True)
    require(0 < amount <= subscription.price_at_purchase, "Số hoàn không hợp lệ")
    settlement = session.scalar(select(BookingSettlement).where(BookingSettlement.booking_id == booking.id).with_for_update())
    destination = owned_wallet(session, booking.customer_id, require_active=False)
    platform_id = platform_wallet(session)
    wallet_ids = [platform_id, destination.id]
    if settlement:
        wallet_ids.append(settlement.tutor_wallet_id)
    locked = lock_wallets(session, *wallet_ids, require_active=False)
    if settlement:
        require(settlement.status == EscrowStatus.HELD, "Quyết toán đã giải ngân hoặc hoàn")
        wallet = locked[settlement.tutor_wallet_id]
        require(wallet.holding_balance >= settlement.hold_amount, "Số dư tạm giữ không khớp")
        wallet.holding_balance -= settlement.hold_amount
        wallet.updated_at = now()
        settlement.status = EscrowStatus.REFUNDED
        # Partial refund terminates the booking; remaining tutor income is paid now.
        remaining = subscription.price_at_purchase - amount
        income = remaining - remaining * settlement.commission_rate // 100
        if income:
            pay_tutor_income(session, wallet, income, subscription.id, admin_id)
    transfer(session, platform_id, destination.id, amount,
             TransactionType.REFUND, subscription_id=subscription.id, admin_id=admin_id,
             allow_inactive_destination=True)
    subscription.status = SubscriptionStatus.CANCELLED
    booking.status, booking.last_updated = BookingStatus.REFUNDED, now()
    for row in session.scalars(select(BookingSession).where(
        BookingSession.booking_id == booking.id, BookingSession.status == BookingSessionStatus.SCHEDULED)):
        row.status, row.updated_at = BookingSessionStatus.CANCELLED, now()


def cancel_booking(session: Session, user_id: UUID, booking_id: UUID) -> Booking:
    booking = accessible_booking(session, user_id, booking_id, lock=True)
    require(booking.customer_id == user_id, "Chỉ khách hàng được hủy đơn", PermissionError)
    if booking.status in {BookingStatus.CANCELLED, BookingStatus.REFUNDED}:
        return booking
    require(booking.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED}, "Sau phân công, hãy mở tranh chấp")
    if booking.subscription_id:
        subscription = get(session, UserSubscription, booking.subscription_id)
        if subscription.price_at_purchase:
            refund_booking(session, booking, subscription.price_at_purchase)
        else:
            subscription.status = SubscriptionStatus.CANCELLED
            booking.status = BookingStatus.CANCELLED
    else:
        booking.status = BookingStatus.CANCELLED
    booking.last_updated = now()
    for row in session.scalars(select(BookingSession).where(BookingSession.booking_id == booking.id)):
        row.status, row.updated_at = BookingSessionStatus.CANCELLED, now()
    return booking
