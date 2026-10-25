from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint("id", "post_id"),
        Index(None, "parent_id", "post_id"),
        ForeignKeyConstraint(["parent_id", "post_id"], ["comments.id", "comments.post_id"]),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="parent_not_self"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    post_id: Mapped[UUID] = mapped_column(ForeignKey("posts.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[UUID | None]
    content: Mapped[str] = mapped_column(Text)
    is_hidden: Mapped[bool | None] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
