from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExternalTransaction(Base):
    __tablename__ = "external_transaction"
    __table_args__ = (
        Index(None, "source_wallet_id"),
        Index(None, "destination_wallet_id"),
        Index(None, "cash_order_id"),
        Index(None, "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    source_wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))
    destination_wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))
    amount: Mapped[int | None] = mapped_column(Integer)
    cash_order_id: Mapped[UUID | None] = mapped_column(ForeignKey("cash_order.id"))
    balance_before: Mapped[int | None] = mapped_column(Integer)
    balance_after: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_admin_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    ref_log_id: Mapped[UUID | None] = mapped_column(ForeignKey("action_logs.id"))
