"""Model: posts. Mẫu: kiểm tra quyền đọc một bài theo role hiện tại trong DB."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Post
from app.models.enums import UserRole
from app.modules.users.user import get_active_user


def get_readable_post(session: Session, post_id: UUID, user_id: UUID | None = None) -> Post:
    role = UserRole.GUEST if user_id is None else get_active_user(session, user_id).role
    if role is None:
        raise PermissionError("User role is not configured")
    level = tuple(UserRole).index(role)
    post = session.get(Post, post_id)
    if post is None or post.is_hidden is not False:
        raise LookupError("Post not found or hidden")
    if post.min_role_level is None or not 0 <= post.min_role_level <= 6:
        raise PermissionError("Post visibility is not configured")
    if level < post.min_role_level:
        raise PermissionError("Role level is insufficient")
    return post


# TODO create_post: xác thực tác giả; snapshot nickname/avatar theo dữ liệu tin cậy;
# kiểm tra title/content, min_role_level 0..6; sanitize nội dung khi hiển thị.
# TODO list/search: áp cùng bộ lọc is_hidden và min_role_level trong SQL TRƯỚC
# phân trang; không tải tất cả rồi lọc quyền ở frontend.
# TODO edit/hide: quyền tác giả/moderator theo policy; khóa hoặc kiểm tra version;
# ghi ActionLog cho thao tác admin; luồng admin xem bài ẩn phải tách riêng.
