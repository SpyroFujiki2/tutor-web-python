from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PaymentMethod(Base):
    __tablename__ = "payment_method"
    __table_args__ = (UniqueConstraint("user_id", "account_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    bank_name: Mapped[str | None] = mapped_column(String)
    account_number: Mapped[str | None] = mapped_column(String)
    account_holder_name: Mapped[str | None] = mapped_column(String)
