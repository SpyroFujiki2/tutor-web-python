from datetime import date
from uuid import UUID

from sqlalchemy import BigInteger, Date, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WalletSnapshot(Base):
    __tablename__ = "wallet_snapshots"
    __table_args__ = (UniqueConstraint("wallet_id", "snapshot_date"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    wallet_id: Mapped[UUID | None] = mapped_column(ForeignKey("wallets.id"))
    snapshot_date: Mapped[date | None] = mapped_column(Date)
    balance_snap: Mapped[int | None] = mapped_column(BigInteger)
    holding_snap: Mapped[int | None] = mapped_column(BigInteger)
    available_snap: Mapped[int | None] = mapped_column(BigInteger)
