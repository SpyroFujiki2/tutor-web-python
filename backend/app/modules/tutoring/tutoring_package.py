"""Tutoring package catalog and audited administrative commands."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TutoringPackage
from app.modules.common import actor, add, audit, get, money, require


def list_active_tutoring_packages(
    session: Session, *, limit: int = 20, offset: int = 0, query: str = "",
) -> list[TutoringPackage]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be between 1 and 100")
    statement = select(TutoringPackage).where(TutoringPackage.is_active.is_(True))
    if query:
        statement = statement.where(TutoringPackage.name.contains(query, autoescape=True))
    return list(session.scalars(statement.order_by(TutoringPackage.price.asc().nulls_last(), TutoringPackage.id)
                               .offset(offset).limit(limit)))


# TODO create/update_package: admin xác thực, kiểm tra giá không âm, tên không rỗng;
# gán UUID và ghi ActionLog cùng transaction khi sửa giá hoặc trạng thái bán.
# TODO deactivate: đổi is_active thay vì xóa gói đã có booking; không sửa snapshot
# title_at_purchase/price_at_purchase của subscription đã mua.
# TODO pagination/search: thêm cursor và bộ lọc khi số gói vượt giới hạn mẫu.


def save_tutoring_package(
    session: Session, admin_id: UUID, values: dict, package_id: UUID | None = None,
) -> TutoringPackage:
    admin = actor(session, admin_id, admin=True)
    require(set(values) == {"name", "price", "is_active"}, "Gói gia sư chỉ nhận name, price, is_active")
    name = values["name"].strip()
    require(0 < len(name) <= 200, "Tên gói phải có 1–200 ký tự")
    price = money(values["price"])
    require(type(values["is_active"]) is bool, "Trạng thái gói không hợp lệ")
    row = get(session, TutoringPackage, package_id, lock=True) if package_id else add(
        session, TutoringPackage, name=name, price=price, is_active=values["is_active"])
    before = {"name": row.name, "price": row.price, "is_active": row.is_active} if package_id else None
    row.name, row.price, row.is_active = name, price, values["is_active"]
    audit(session, admin, row, "tutoring_package.save", before=before, operation='POST' if package_id is None else 'PUT',
          after={"name": name, "price": price, "is_active": row.is_active})
    return row


def deactivate_tutoring_package(session: Session, admin_id: UUID, package_id: UUID) -> TutoringPackage:
    admin = actor(session, admin_id, admin=True)
    row = get(session, TutoringPackage, package_id, lock=True)
    if row.is_active:
        row.is_active = False
        audit(session, admin, row, "tutoring_package.deactivate", after={"is_active": False})
    return row
