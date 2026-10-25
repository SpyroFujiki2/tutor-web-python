from uuid import UUID

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TutoringPackage(Base):
    __tablename__ = "tutoring_package"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    price: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool | None] = mapped_column(Boolean)
