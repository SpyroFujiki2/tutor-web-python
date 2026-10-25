from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RequestStatus, request_status_enum


class CommentReport(Base):
    __tablename__ = "comment_report"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    reporter_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[UUID | None] = mapped_column(ForeignKey("comments.id"))
    reason_category: Mapped[str | None] = mapped_column(String)
    reason_details: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int | None] = mapped_column(Integer)
    admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[RequestStatus | None] = mapped_column(request_status_enum, server_default=text("'pending'"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
