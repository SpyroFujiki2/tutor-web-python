from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        UniqueConstraint("course_id", "order_idx"),
        UniqueConstraint("id", "course_id"),
        CheckConstraint("session_count IS NULL OR session_count > 0", name="positive_session_count"),
        CheckConstraint("duration_minutes IS NULL OR duration_minutes > 0", name="positive_duration_minutes"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"))
    order_idx: Mapped[int] = mapped_column(Integer)
    media_url: Mapped[str | None] = mapped_column(String)
    assignment_url: Mapped[str | None] = mapped_column(String)
    session_count: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
