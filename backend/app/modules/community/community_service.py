"""Community visibility, immutable reply parents and moderated role promotion."""

from datetime import timedelta

from sqlalchemy import func, select

from app.models import Comment, CommentReport, Post, RoleRequest, User
from app.models.enums import RequestStatus, UserRole
from app.modules.common import ADMIN_ROLES, RateLimitError, actor, add, audit, get, now, require
from app.modules.community.post import get_readable_post, list_readable_posts


def list_posts(session, user_id, *, limit=20, offset=0, query="", before_id=None):
    return list_readable_posts(session, user_id, limit=limit, offset=offset, query=query, before_id=before_id)


def save_post(session, user_id, values, post_id=None):
    user = actor(session, user_id)
    require(values["min_role_level"] <= tuple(UserRole).index(user.role), "Không thể tạo bài trên cấp của mình")
    if post_id is None:
        # User schema has no public nickname/avatar; do not expose their email.
        return add(session, Post, author_id=user_id, author_nickname=f"Thành viên {str(user_id)[:8]}",
                   **values, is_hidden=False, created_at=now())
    row = get(session, Post, post_id, lock=True)
    require(row.author_id == user_id and row.is_hidden is False, "Không được sửa bài viết", PermissionError)
    for key, value in values.items():
        setattr(row, key, value)
    return row


def create_comment(session, user_id, post_id, content, parent_id=None):
    actor(session, user_id)
    get_readable_post(session, post_id, user_id)
    if parent_id:
        parent = get(session, Comment, parent_id)
        require(parent.post_id == post_id and parent.is_hidden is False, "Bình luận cha không hợp lệ")
    # Parent is immutable after creation, so cycles cannot be introduced.
    return add(session, Comment, post_id=post_id, user_id=user_id, parent_id=parent_id,
               content=content, is_hidden=False, created_at=now())


def edit_comment(session, user_id, comment_id, content):
    actor(session, user_id)
    row = get(session, Comment, comment_id, lock=True)
    get_readable_post(session, row.post_id, user_id)
    require(row.user_id == user_id and row.is_hidden is False, "Không được sửa bình luận", PermissionError)
    row.content = content
    return row


def hide_content(session, user_id, model, identity, hidden, reason):
    user = actor(session, user_id)
    row = get(session, model, identity, lock=True)
    owner_id = row.author_id if model is Post else row.user_id
    require(user.role in ADMIN_ROLES or (owner_id == user_id and hidden), "Không đủ quyền kiểm duyệt", PermissionError)
    row.is_hidden = hidden
    if user.role in ADMIN_ROLES:
        audit(session, user, row, "content.visibility", after={"is_hidden": hidden}, reason=reason)
    return row


def submit_report(session, user_id, comment_id, values):
    category = values["reason_category"].strip()
    details = values.get("reason_details", "").strip()
    require(0 < len(category) <= 200 and len(details) <= 2000, "Lý do báo cáo không hợp lệ")
    actor(session, user_id, lock=True)
    comment = get(session, Comment, comment_id)
    get_readable_post(session, comment.post_id, user_id)
    require(comment.is_hidden is False, "Bình luận đã ẩn", LookupError)
    existing = session.scalar(select(CommentReport).where(
        CommentReport.reporter_id == user_id, CommentReport.target_id == comment_id,
        CommentReport.status == RequestStatus.PENDING))
    if existing:
        return existing
    count = session.scalar(select(func.count()).select_from(CommentReport).where(
        CommentReport.reporter_id == user_id, CommentReport.created_at > now() - timedelta(minutes=1)))
    require(count < 5, "Bạn gửi báo cáo quá nhanh; hãy chờ một phút", RateLimitError)
    return add(session, CommentReport, reporter_id=user_id, target_id=comment_id,
               reason_category=category, reason_details=details,
               priority=0, status=RequestStatus.PENDING, created_at=now())


def claim_report(session, admin_id, report_id):
    admin = actor(session, admin_id, admin=True)
    row = get(session, CommentReport, report_id, lock=True)
    comment = get(session, Comment, row.target_id)
    require(admin_id not in {row.reporter_id, comment.user_id}, "Không tự xử lý báo cáo liên quan")
    require(row.status == RequestStatus.PENDING and row.admin_id in {None, admin_id}, "Báo cáo đã được nhận hoặc đóng")
    row.admin_id, row.locked_at = admin_id, now()
    audit(session, admin, row, "report.claim")
    return row


def resolve_report(session, admin_id, report_id, approve, reason):
    admin = actor(session, admin_id, admin=True)
    row = get(session, CommentReport, report_id, lock=True)
    require(row.status == RequestStatus.PENDING and row.admin_id == admin_id, "Báo cáo chưa giao cho bạn hoặc đã đóng")
    row.status = RequestStatus.APPROVED if approve else RequestStatus.REJECTED
    if approve:
        get(session, Comment, row.target_id, lock=True).is_hidden = True
    audit(session, admin, row, "report.resolve", after={"status": row.status}, reason=reason)
    return row


def submit_role_request(session, user_id, values):
    user = actor(session, user_id, lock=True)
    roles = tuple(UserRole)
    require(user.role is not None and user.role != UserRole.HEAD_ADMIN, "Không còn bậc để nâng")
    existing = session.scalar(select(RoleRequest).where(RoleRequest.user_id == user_id,
                                                       RoleRequest.status == RequestStatus.PENDING))
    require(existing is None, "Đã có yêu cầu đang chờ")
    return add(session, RoleRequest, user_id=user_id, current_role_at_request=user.role,
               question_set=roles.index(user.role) + 1, **values, status=RequestStatus.PENDING,
               priority=0, created_at=now(), updated_at=now())


def decide_role_request(session, admin_id, request_id, approve, reason):
    admin = actor(session, admin_id, admin=True)
    initial = get(session, RoleRequest, request_id)
    user = get(session, User, initial.user_id, lock=True)
    row = get(session, RoleRequest, request_id, lock=True)
    require(user.id != admin_id, "Không tự duyệt yêu cầu")
    require(row.status == RequestStatus.PENDING, "Yêu cầu đã xử lý")
    roles = tuple(UserRole)
    requested_role = row.current_role_at_request
    require(requested_role is not None and requested_role != UserRole.HEAD_ADMIN, "Bậc yêu cầu không hợp lệ")
    next_role = roles[roles.index(requested_role) + 1]
    require(admin.role == UserRole.HEAD_ADMIN or roles.index(next_role) < roles.index(admin.role),
            "Cần quản trị cấp cao duyệt bậc này", PermissionError)
    if approve:
        actor(session, user.id)
        require(user.role == requested_role, "Vai trò đã thay đổi; hãy từ chối và tạo yêu cầu mới")
    row.admin_id, row.admin_note, row.updated_at = admin_id, reason, now()
    row.status = RequestStatus.APPROVED if approve else RequestStatus.REJECTED
    if approve:
        user.role = next_role
    audit(session, admin, row, "role.decide", before={"role": row.current_role_at_request},
          after={"role": user.role, "status": row.status}, reason=reason)
    return row
