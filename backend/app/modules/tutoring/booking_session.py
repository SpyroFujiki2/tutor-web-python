"""Booking sessions: timezone validation, scheduling, conflicts and attendance."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Booking, BookingSession
from app.models.enums import BookingSessionStatus, BookingStatus
from app.modules.common import ADMIN_ROLES, actor, add, get, now, require
from app.modules.tutoring.access import accessible_booking


def list_booking_sessions(session: Session, booking_id: UUID, user_id: UUID) -> list[BookingSession]:
    accessible_booking(session, user_id, booking_id)
    return list(session.scalars(
        select(BookingSession).where(BookingSession.booking_id == booking_id)
        .order_by(BookingSession.session_no)
    ))


# TODO schedule: kiểm tra quyền, khóa booking/tutor theo thứ tự thống nhất; kiểm tra
# session_no > 0, thời gian đủ cặp và ends_at > starts_at; tìm lịch giao nhau.
# TODO add/cancel_session: giữ ít nhất một buổi hợp lệ theo chính sách đã chốt;
# Unique(booking_id, session_no) là lớp bảo vệ khi tạo đồng thời.
# TODO complete_session: cập nhật updated_at tường minh; chỉ hoàn tất booking khi
# đủ điều kiện tất cả buổi và không còn tranh chấp chặn quyết toán.


def session_values(values: dict) -> dict:
    values = dict(values)
    start, end = values.get("starts_at"), values.get("ends_at")
    require((start is None) == (end is None), "Cần cả giờ bắt đầu và kết thúc")
    if start is not None:
        require(isinstance(start, datetime) and isinstance(end, datetime)
                and start.tzinfo is not None and end.tzinfo is not None and end > start,
                "Khoảng thời gian phải hợp lệ và kèm múi giờ")
    for key in ("starts_at", "ends_at"):
        if values.get(key) is not None:
            values[key] = values[key].astimezone(UTC).replace(tzinfo=None)
    return values


def check_schedule(session: Session, booking: Booking, starts_at: datetime | None, ends_at: datetime | None, *, exclude: UUID | None=None) -> None:
    if starts_at is None or booking.tutor_id is None:
        return
    actor(session, booking.tutor_id, lock=True)
    conflict = select(BookingSession.id).join(Booking, Booking.id == BookingSession.booking_id).where(
        Booking.tutor_id == booking.tutor_id,
        Booking.status.in_([BookingStatus.ASSIGNED, BookingStatus.DISPUTING]),
        BookingSession.status != BookingSessionStatus.CANCELLED,
        BookingSession.starts_at < ends_at, BookingSession.ends_at > starts_at,
    )
    if exclude:
        conflict = conflict.where(BookingSession.id != exclude)
    require(session.scalar(conflict.limit(1)) is None, "Gia sư đã có lịch trong khoảng thời gian này")


def schedule_session(session: Session, user_id: UUID, booking_id: UUID, values: dict, session_id: UUID | None=None) -> BookingSession:
    user = actor(session, user_id)
    booking = accessible_booking(session, user_id, booking_id, lock=True, administration=True)
    require(user.role in ADMIN_ROLES or booking.tutor_id == user_id, "Cần gia sư hoặc quản trị", PermissionError)
    require(booking.status == BookingStatus.ASSIGNED, "Đơn chưa phân công hoặc đã đóng")
    data = session_values(values)
    require(data.get("starts_at") is not None and data["starts_at"] > now(), "Cần lịch học trong tương lai")
    row = get(session, BookingSession, session_id, lock=True) if session_id else None
    if row:
        require(row.booking_id == booking_id and row.status == BookingSessionStatus.SCHEDULED, "Buổi học không thể sửa")
    check_schedule(session, booking, data["starts_at"], data["ends_at"], exclude=session_id)
    if row:
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = now()
    else:
        number = session.scalar(select(func.max(BookingSession.session_no)).where(BookingSession.booking_id == booking_id)) or 0
        require(number < 100, "Mỗi đơn có tối đa 100 buổi học")
        row = add(session, BookingSession, booking_id=booking_id, session_no=number + 1, **data,
                  status=BookingSessionStatus.SCHEDULED, created_at=now(), updated_at=now())
    return row


def session_action(session: Session, user_id: UUID, booking_id: UUID, session_id: UUID, action: str) -> BookingSession:
    require(action in {"complete", "cancel"}, "Thao tác buổi học không hợp lệ")
    user = actor(session, user_id)
    booking = accessible_booking(session, user_id, booking_id, lock=True, administration=True)
    require(user.role in ADMIN_ROLES or booking.tutor_id == user_id, "Cần gia sư hoặc quản trị", PermissionError)
    require(booking.status == BookingStatus.ASSIGNED, "Đơn không hoạt động")
    row = get(session, BookingSession, session_id, lock=True)
    require(row.booking_id == booking_id, "Buổi học không thuộc đơn", LookupError)
    target = BookingSessionStatus.COMPLETED if action == "complete" else BookingSessionStatus.CANCELLED
    if row.status == target:
        return row
    require(row.status == BookingSessionStatus.SCHEDULED, "Buổi học đã kết thúc")
    if action == "complete":
        require(row.ends_at is not None and row.ends_at <= now(), "Buổi học chưa kết thúc")
    else:
        count = session.scalar(select(func.count()).select_from(BookingSession).where(
            BookingSession.booking_id == booking_id, BookingSession.status != BookingSessionStatus.CANCELLED))
        require(count > 1, "Phải giữ ít nhất một buổi học")
    row.status, row.updated_at = target, now()
    return row
