from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKeyConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        ForeignKeyConstraint(
            ["subscription_id", "course_id"],
            ["course_progress.subscription_id", "course_progress.course_id"],
        ),
        ForeignKeyConstraint(["lesson_id", "course_id"], ["lessons.id", "lessons.course_id"]),
        CheckConstraint("duration_watched >= 0", name="nonnegative_duration_watched"),
    )

    subscription_id: Mapped[UUID] = mapped_column(primary_key=True)
    course_id: Mapped[UUID]
    lesson_id: Mapped[UUID] = mapped_column(primary_key=True)
    is_absent: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    duration_watched: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    assignment_completed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
