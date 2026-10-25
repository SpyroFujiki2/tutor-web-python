from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import TransactionType, transaction_type_enum


class InternalTransaction(Base):
    __tablename__ = "internal_transaction"
    __table_args__ = (
        Index(None, "source_wallet_id"),
        Index(None, "destination_wallet_id"),
        Index(None, "subscription_id"),
        Index(None, "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    source_wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"))
    destination_wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"))
    amount: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[TransactionType | None] = mapped_column(transaction_type_enum)
    subscription_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_subscriptions.id"))
    source_balance_before: Mapped[int | None] = mapped_column(Integer)
    source_balance_after: Mapped[int | None] = mapped_column(Integer)
    destination_balance_before: Mapped[int | None] = mapped_column(Integer)
    destination_balance_after: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String)
    created_by_admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    ref_log_id: Mapped[UUID | None] = mapped_column(ForeignKey("action_logs.id"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
