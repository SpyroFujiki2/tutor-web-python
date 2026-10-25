from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import ServiceType, SubscriptionStatus, service_type_enum, subscription_status_enum


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (Index(None, "user_id", "status"), Index(None, "type"))

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[ServiceType] = mapped_column(service_type_enum)
    title_at_purchase: Mapped[str | None] = mapped_column(String)
    price_at_purchase: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[SubscriptionStatus | None] = mapped_column(subscription_status_enum, server_default=text("'active'"))
    activated_at: Mapped[datetime] = mapped_column(DateTime)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime)
