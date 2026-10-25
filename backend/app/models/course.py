from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CourseStatus, course_status_enum


class Course(Base):
    __tablename__ = "courses"

    status: Mapped[CourseStatus] = mapped_column(course_status_enum, server_default=text("'visible'"))
    id: Mapped[UUID] = mapped_column(primary_key=True)
    price: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    is_live: Mapped[bool | None] = mapped_column(Boolean)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
