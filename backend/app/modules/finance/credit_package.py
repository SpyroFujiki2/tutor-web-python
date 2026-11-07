"""Credit/VND package catalog with audited changes and immutable order quotes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreditPackage
from app.modules.common import actor, add, audit, get, money, require


def list_active_credit_packages(session: Session, *, limit: int = 20, offset: int = 0, query: str = '') -> list[CreditPackage]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("limit must be between 1 and 100")
    statement = select(CreditPackage).where(CreditPackage.is_active.is_(True))
    if query:
        statement = statement.where(CreditPackage.name.contains(query, autoescape=True))
    return list(session.scalars(statement.order_by(CreditPackage.price.asc().nulls_last(), CreditPackage.id).offset(offset).limit(limit)))


# TODO create/update: admin kiểm tra credits/price dương theo chính sách, cấp UUID;
# log thay đổi; phân biệt giá VND và số credit, không dùng chung hai đơn vị.
# TODO deactivate: không xóa gói đã có cash_order; amount_vnd/credit_amount ở đơn
# là snapshot lúc đặt và không bị thay đổi khi sửa bảng giá.
# TODO promotions: chốt giá/khuyến mại tại server; không nhận số credit nhận được
# hoặc tỷ giá quy đổi do client tự tính.


def save_credit_package(session: Session, admin_id: UUID, values: dict, package_id: UUID | None = None) -> CreditPackage:
    admin = actor(session, admin_id, admin=True)
    require(set(values) == {'name', 'credits', 'price', 'is_active'}, 'Trường gói nạp không hợp lệ')
    name = values['name'].strip()
    require(0 < len(name) <= 200 and type(values['is_active']) is bool, 'Tên/trạng thái gói không hợp lệ')
    require(money(values['credits']) > 0 and money(values['price']) > 0, 'Giá VND và số credit phải dương')
    row = get(session, CreditPackage, package_id, lock=True) if package_id else add(session, CreditPackage, **{**values, 'name': name})
    before = {key: getattr(row, key) for key in values} if package_id else None
    for key, value in {**values, 'name': name}.items():
        setattr(row, key, value)
    audit(session, admin, row, 'credit_package.save', before=before, after={**values, 'name': name}, operation='POST' if package_id is None else 'PUT')
    return row


def deactivate_credit_package(session: Session, admin_id: UUID, package_id: UUID) -> CreditPackage:
    admin = actor(session, admin_id, admin=True)
    row = get(session, CreditPackage, package_id, lock=True)
    if row.is_active:
        row.is_active = False
        audit(session, admin, row, 'credit_package.deactivate', after={'is_active': False})
    return row
