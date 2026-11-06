"""Model: posts. Mẫu: kiểm tra quyền đọc một bài theo role hiện tại trong DB."""

from uuid import UUID

from sqlalchemy import and_, or_, select
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


def list_readable_posts(
    session: Session, user_id: UUID | None = None, *, limit: int = 20, offset: int = 0,
    query: str = "", before_id: UUID | None = None,
) -> list[Post]:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Invalid pagination")
    role = UserRole.GUEST if user_id is None else get_active_user(session, user_id).role
    if role is None:
        raise PermissionError("User role is not configured")
    statement = select(Post).where(Post.is_hidden.is_(False), Post.min_role_level >= 0,
                                    Post.min_role_level <= tuple(UserRole).index(role))
    if query:
        statement = statement.where(Post.title.contains(query, autoescape=True))
    if before_id:
        pivot = get_readable_post(session, before_id, user_id)
        if pivot.created_at is None:
            statement = statement.where(Post.created_at.is_(None), Post.id > pivot.id)
        else:
            statement = statement.where(or_(Post.created_at < pivot.created_at, Post.created_at.is_(None),
                                            and_(Post.created_at == pivot.created_at, Post.id > pivot.id)))
    return list(session.scalars(statement.order_by(Post.created_at.desc().nulls_last(), Post.id).offset(offset).limit(limit)))
