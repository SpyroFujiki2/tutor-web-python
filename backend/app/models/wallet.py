from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import WalletType, wallet_type_enum


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("user_id", "type"),
        CheckConstraint("available_balance >= 0 AND holding_balance >= 0 AND debt >= 0", name="nonnegative_balances"),
        CheckConstraint("commission_rate IS NULL OR (commission_rate >= 0 AND commission_rate <= 100)", name="commission_range"),
        CheckConstraint(
            "type = 'commercial' OR (holding_balance = 0 AND debt = 0 AND commission_rate IS NULL AND contract_id IS NULL)",
            name="normal_wallet_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[WalletType] = mapped_column(wallet_type_enum)
    available_balance: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    holding_balance: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    debt: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    commission_rate: Mapped[int | None] = mapped_column(Integer)
    contract_id: Mapped[str | None] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
