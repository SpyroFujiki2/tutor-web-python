"""Model: user_subscriptions. Mẫu: đọc quyền truy cập còn hiệu lực của user."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import UserSubscription
from app.models.enums import SubscriptionStatus
from app.modules.users.user import get_active_user


def list_my_active_subscriptions(session: Session, user_id: UUID) -> list[UserSubscription]:
    get_active_user(session, user_id)
    now = datetime.now(UTC).replace(tzinfo=None)
    statement = (
        select(UserSubscription)
        .where(
            UserSubscription.user_id == user_id,
            UserSubscription.status == SubscriptionStatus.ACTIVE,
            UserSubscription.activated_at <= now,
            or_(UserSubscription.expired_at.is_(None), UserSubscription.expired_at > now),
        )
        .order_by(UserSubscription.activated_at.desc(), UserSubscription.id)
    )
    return list(session.scalars(statement))


# TODO activate: chỉ tạo sau khi xác nhận thanh toán; snapshot title/price từ DB,
# không nhận giá client; type phải khớp Booking hoặc CourseProgress liên kết.
# TODO expire: job cập nhật active -> expired khi hết hạn; mọi kiểm tra quyền
# vẫn phải xét thời gian thực để không phụ thuộc việc job đã chạy hay chưa.
# TODO cancel/refund: khóa subscription, cập nhật quyền và giao dịch bù cùng
# transaction; không dùng việc ẩn Course để hủy quyền đã mua.
