from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import BookingSessionStatus, booking_session_status_enum


class BookingSession(Base):
    __tablename__ = "booking_sessions"
    __table_args__ = (
        UniqueConstraint("booking_id", "session_no"),
        Index(None, "starts_at"),
        CheckConstraint("session_no > 0", name="positive_session_no"),
        CheckConstraint(
            "(starts_at IS NULL AND ends_at IS NULL) OR "
            "(starts_at IS NOT NULL AND ends_at IS NOT NULL AND ends_at > starts_at)",
            name="valid_session_interval",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.id"))
    session_no: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime)
    meeting_url: Mapped[str | None] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BookingSessionStatus] = mapped_column(booking_session_status_enum, server_default=text("'scheduled'"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
