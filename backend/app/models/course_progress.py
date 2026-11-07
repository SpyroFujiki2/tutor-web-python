from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import CourseResult, course_result_enum


class CourseProgress(Base):
    __tablename__ = "course_progress"
    __table_args__ = (
        Index(None, "course_id"),
        UniqueConstraint("subscription_id", "course_id"),
        CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="progress_range"),
        CheckConstraint(
            "attendance_ratio IS NULL OR (attendance_ratio >= 0 AND attendance_ratio <= 1)",
            name="attendance_ratio_range",
        ),
        CheckConstraint(
            "(progress_percent < 100 AND result IS NULL AND completed_at IS NULL) OR "
            "(progress_percent = 100 AND completed_at IS NOT NULL AND "
            "((result IS NULL AND final_score IS NULL) OR (result IS NOT NULL AND final_score IS NOT NULL)))",
            name="completion_requires_result",
        ),
    )

    subscription_id: Mapped[UUID] = mapped_column(ForeignKey("user_subscriptions.id"), primary_key=True)
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"))
    progress_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("0"))
    attendance_ratio: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    midterm_score: Mapped[int | None] = mapped_column(Integer)
    endterm_score: Mapped[int | None] = mapped_column(Integer)
    practice_score: Mapped[int | None] = mapped_column(Integer)
    final_score: Mapped[int | None] = mapped_column(Integer)
    result: Mapped[CourseResult | None] = mapped_column(course_result_enum)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
