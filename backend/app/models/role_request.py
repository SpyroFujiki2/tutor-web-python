from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RequestStatus, UserRole, request_status_enum, user_role_enum


class RoleRequest(Base):
    __tablename__ = "role_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    current_role_at_request: Mapped[UserRole | None] = mapped_column(user_role_enum)
    question_set: Mapped[int | None] = mapped_column(Integer)
    answer_url: Mapped[str | None] = mapped_column(String)
    request_note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RequestStatus | None] = mapped_column(request_status_enum, server_default=text("'pending'"))
    priority: Mapped[int | None] = mapped_column(Integer)
    admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
