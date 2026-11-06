"""Booking disputes: scoped access, case assignment and atomic resolution."""


from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Booking, BookingSession, BookingSettlement, Dispute, UserSubscription
from app.models.enums import (
    BookingSessionStatus,
    BookingStatus,
    DisputeVerdict,
    EscrowStatus,
    SubscriptionStatus,
)
from app.modules.common import actor, add, audit, get, money, now, require
from app.modules.tutoring.access import accessible_booking
from app.modules.tutoring.booking import refund_booking


def get_booking_dispute(session: Session, booking_id: UUID, user_id: UUID) -> Dispute | None:
    accessible_booking(session, user_id, booking_id)
    return session.scalar(select(Dispute).where(Dispute.booking_id == booking_id))


# TODO raise_dispute: kiểm tra người mở thuộc booking và trạng thái cho phép;
# khóa booking, tạo duy nhất một Dispute, đổi booking.status trong cùng transaction.
# TODO assign_admin: xác thực vai trò/phạm vi phân công; quyền đọc booking/messages
# của admin phải dựa trên dispute được giao, không chỉ role=admin.
# TODO resolve: chốt verdict và số tiền hoàn khi partial, khóa booking/settlement/ví;
# tạo giao dịch bù, cập nhật subscription/quyết toán, resolve_at và ActionLog nguyên tử.
# TODO retry: xác định idempotency trước khi nối luồng hoàn tiền thật.


def open_dispute(session: Session, user_id: UUID, booking_id: UUID, reason: str) -> Dispute:
    require(isinstance(reason, str) and 0 < len(reason.strip()) <= 200, "Lý do tranh chấp không hợp lệ")
    booking = accessible_booking(session, user_id, booking_id, lock=True)
    existing = session.scalar(select(Dispute).where(Dispute.booking_id == booking_id))
    if existing:
        require(not existing.is_completed, "Tranh chấp của đơn đã được giải quyết")
        return existing
    require(booking.status in {BookingStatus.CONFIRMED, BookingStatus.ASSIGNED, BookingStatus.COMPLETED}, "Đơn không thể tranh chấp")
    settlement = session.scalar(select(BookingSettlement).where(BookingSettlement.booking_id == booking_id))
    require(not settlement or (settlement.status == EscrowStatus.HELD and settlement.release_date is not None
                              and settlement.release_date > now()),
            "Đã hết thời hạn tranh chấp")
    booking.status, booking.last_updated = BookingStatus.DISPUTING, now()
    return add(session, Dispute, booking_id=booking_id, raised_by_user_id=user_id,
               reason_category=reason.strip(), is_completed=False, created_at=now())


def dispute_access(session: Session, user_id: UUID, dispute_id: UUID) -> Dispute:
    actor(session, user_id)
    dispute = session.get(Dispute, dispute_id, populate_existing=True)
    require(dispute is not None, "Không tìm thấy tranh chấp", LookupError)
    booking = get(session, Booking, dispute.booking_id)
    require(user_id in {booking.customer_id, booking.tutor_id, dispute.admin_id}, "Không tìm thấy tranh chấp", LookupError)
    return dispute


def claim_dispute(session: Session, admin_id: UUID, dispute_id: UUID) -> Dispute:
    admin = actor(session, admin_id, admin=True)
    dispute = get(session, Dispute, dispute_id, lock=True)
    booking = get(session, Booking, dispute.booking_id)
    require(admin_id not in {booking.customer_id, booking.tutor_id}, "Không tự xử lý tranh chấp liên quan")
    require(not dispute.is_completed and dispute.admin_id in {None, admin_id}, "Tranh chấp đã được nhận hoặc đóng")
    dispute.admin_id = admin.id
    audit(session, admin, dispute, "dispute.claim")
    return dispute


def resolve_dispute(session: Session, admin_id: UUID, dispute_id: UUID, verdict: DisputeVerdict, refund_amount: int, reason: str) -> Dispute:
    require(verdict in tuple(DisputeVerdict), "Kết luận tranh chấp không hợp lệ")
    money(refund_amount)
    require(isinstance(reason, str) and 0 < len(reason.strip()) <= 200, "Cần ghi lý do giải quyết")
    admin = actor(session, admin_id, admin=True)
    # Match booking -> dispute -> wallet order used by release/refund.
    initial = get(session, Dispute, dispute_id)
    booking = get(session, Booking, initial.booking_id, lock=True)
    dispute = get(session, Dispute, dispute_id, lock=True)
    require(dispute.admin_id == admin_id, "Tranh chấp chưa giao cho bạn", PermissionError)
    require(admin_id not in {booking.customer_id, booking.tutor_id}, "Không tự xử lý tranh chấp liên quan", PermissionError)
    require(not dispute.is_completed, "Tranh chấp đã đóng")
    require(booking.status == BookingStatus.DISPUTING, "Đơn không trong tranh chấp")
    subscription = get(session, UserSubscription, booking.subscription_id)
    if verdict == DisputeVerdict.REJECTED:
        require(refund_amount == 0, "Từ chối tranh chấp không kèm hoàn tiền")
        settled = session.scalar(select(BookingSettlement.id).where(BookingSettlement.booking_id == booking.id))
        booking.status = BookingStatus.COMPLETED if settled else BookingStatus.ASSIGNED if booking.tutor_id else BookingStatus.CONFIRMED
    else:
        amount = subscription.price_at_purchase if verdict == DisputeVerdict.REFUND_FULL else refund_amount
        if verdict == DisputeVerdict.REFUND_PARTIAL:
            require(0 < amount < subscription.price_at_purchase, "Hoàn một phần phải nhỏ hơn tổng tiền")
            require(session.scalar(select(BookingSettlement.id).where(BookingSettlement.booking_id == booking.id)),
                    "Chỉ hoàn một phần sau khi đã có quyết toán; đơn chưa hoàn thành có thể hoàn toàn bộ")
        if amount:
            refund_booking(session, booking, amount, admin_id=admin_id)
        else:
            subscription.status, booking.status = SubscriptionStatus.CANCELLED, BookingStatus.REFUNDED
            settlement = session.scalar(select(BookingSettlement).where(
                BookingSettlement.booking_id == booking.id).with_for_update())
            if settlement:
                require(settlement.status == EscrowStatus.HELD and settlement.tutor_income == 0,
                        "Quyết toán không hợp lệ cho đơn miễn phí")
                settlement.status = EscrowStatus.REFUNDED
            for row in session.scalars(select(BookingSession).where(
                BookingSession.booking_id == booking.id, BookingSession.status == BookingSessionStatus.SCHEDULED)):
                row.status, row.updated_at = BookingSessionStatus.CANCELLED, now()
    booking.last_updated = now()
    dispute.verdict, dispute.is_completed, dispute.resolve_at = verdict, True, now()
    audit(session, admin, dispute, "dispute.resolve", after={"verdict": verdict,
          "refund_amount": 0 if verdict == DisputeVerdict.REJECTED else amount}, reason=reason)
    return dispute
