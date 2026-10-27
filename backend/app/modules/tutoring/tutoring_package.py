"""Model: tutoring_package. Mẫu: đọc danh sách gói đang bán."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TutoringPackage


def list_active_tutoring_packages(session: Session, *, limit: int = 20) -> list[TutoringPackage]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    return list(session.scalars(
        select(TutoringPackage).where(TutoringPackage.is_active.is_(True))
        .order_by(TutoringPackage.price.asc().nulls_last(), TutoringPackage.id).limit(limit)
    ))


# TODO create/update_package: admin xác thực, kiểm tra giá không âm, tên không rỗng;
# gán UUID và ghi ActionLog cùng transaction khi sửa giá hoặc trạng thái bán.
# TODO deactivate: đổi is_active thay vì xóa gói đã có booking; không sửa snapshot
# title_at_purchase/price_at_purchase của subscription đã mua.
# TODO pagination/search: thêm cursor và bộ lọc khi số gói vượt giới hạn mẫu.
