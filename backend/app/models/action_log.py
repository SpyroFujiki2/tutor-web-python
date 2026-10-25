from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActionLog(Base):
    __tablename__ = "action_logs"
    __table_args__ = (Index(None, "target_user_id"), Index(None, "target_id"), Index(None, "created_at"))

    id: Mapped[UUID] = mapped_column(primary_key=True)
    admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[UUID | None]
    action_code: Mapped[str | None] = mapped_column(String)
    old_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
