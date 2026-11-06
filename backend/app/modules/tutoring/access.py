"""Shared booking visibility policy."""


from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Booking
from app.modules.common import ADMIN_ROLES, actor, get, require


def accessible_booking(session: Session, user_id: UUID, booking_id: UUID, *, lock: bool=False, administration: bool=False) -> Booking:
    user = actor(session, user_id)
    booking = get(session, Booking, booking_id, lock=lock)
    require(user.id in (booking.customer_id, booking.tutor_id) or
            (administration and user.role in ADMIN_ROLES), "Không tìm thấy đơn học", LookupError)
    return booking
