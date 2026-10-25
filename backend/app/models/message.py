from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        ForeignKeyConstraint(["dispute_id", "booking_id"], ["disputes.id", "disputes.booking_id"]),
        Index(None, "booking_id", "created_at"),
        Index(None, "dispute_id", "created_at"),
        CheckConstraint("content IS NOT NULL OR file_url IS NOT NULL", name="content_or_file"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.id"))
    dispute_id: Mapped[UUID | None]
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str | None] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
