"""Model: credit_package. Mẫu: đọc các gói nạp đang được bán."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CreditPackage


def list_active_credit_packages(session: Session, *, limit: int = 20) -> list[CreditPackage]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return list(session.scalars(
        select(CreditPackage).where(CreditPackage.is_active.is_(True))
        .order_by(CreditPackage.price.asc().nulls_last(), CreditPackage.id).limit(limit)
    ))


# TODO create/update: admin kiểm tra credits/price dương theo chính sách, cấp UUID;
# log thay đổi; phân biệt giá VND và số credit, không dùng chung hai đơn vị.
# TODO deactivate: không xóa gói đã có cash_order; amount_vnd/credit_amount ở đơn
# là snapshot lúc đặt và không bị thay đổi khi sửa bảng giá.
# TODO promotions: chốt giá/khuyến mại tại server; không nhận số credit nhận được
# hoặc tỷ giá quy đổi do client tự tính.
