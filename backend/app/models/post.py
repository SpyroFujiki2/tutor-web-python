from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    author_nickname: Mapped[str | None] = mapped_column(String)
    author_avatar_url: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    content: Mapped[str | None] = mapped_column(Text)
    min_role_level: Mapped[int | None] = mapped_column(Integer)
    is_hidden: Mapped[bool | None] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
