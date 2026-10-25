from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import EscrowStatus, escrow_status_enum


class BookingSettlement(Base):
    __tablename__ = "booking_settlements"
    __table_args__ = (
        Index(None, "tutor_wallet_id", "status"),
        Index(None, "release_date"),
        CheckConstraint(
            "total_amount >= 0 AND platform_fee >= 0 AND tutor_income >= 0 AND available_amount >= 0 AND hold_amount >= 0",
            name="nonnegative_amounts",
        ),
        CheckConstraint("commission_rate >= 0 AND commission_rate <= 100", name="commission_range"),
        CheckConstraint("total_amount = platform_fee + tutor_income", name="total_allocation"),
        CheckConstraint("tutor_income = available_amount + hold_amount", name="income_allocation"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    booking_id: Mapped[UUID] = mapped_column(ForeignKey("booking.id"), unique=True)
    tutor_wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"))
    total_amount: Mapped[int] = mapped_column(BigInteger)
    commission_rate: Mapped[int] = mapped_column(Integer)
    platform_fee: Mapped[int] = mapped_column(BigInteger)
    tutor_income: Mapped[int] = mapped_column(BigInteger)
    available_amount: Mapped[int] = mapped_column(BigInteger)
    hold_amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[EscrowStatus] = mapped_column(escrow_status_enum, server_default=text("'held'"))
    release_date: Mapped[datetime | None] = mapped_column(DateTime)
    actual_released_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("now()"))
