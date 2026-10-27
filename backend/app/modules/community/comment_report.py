"""Model: comment_report. Mẫu: báo cáo một bình luận mà user được phép đọc."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import Comment, CommentReport
from app.models.enums import RequestStatus
from app.modules.community.post import get_readable_post
from app.modules.users.user import get_active_user


def report_comment(
    session: Session, *, reporter_id: UUID, comment_id: UUID, reason_category: str,
) -> CommentReport:
    get_active_user(session, reporter_id)
    comment = session.get(Comment, comment_id)
    if comment is None or comment.is_hidden is not False:
        raise LookupError("Comment not found or hidden")
    get_readable_post(session, comment.post_id, reporter_id)
    if not reason_category.strip():
        raise ValueError("Report reason is required")
    report = CommentReport(
        id=uuid4(), reporter_id=reporter_id, target_id=comment_id,
        reason_category=reason_category.strip(), status=RequestStatus.PENDING,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    session.add(report)
    session.flush()
    return report


# TODO submit_details: schema giới hạn reason/category; thêm rate limit và chốt
# chính sách báo cáo trùng trước khi đưa hàm mẫu ra endpoint công khai.
# TODO claim_report: kiểm tra moderator; khóa pending report, gán admin_id và
# locked_at; dùng row lock/skip_locked cho hàng đợi nhiều admin.
# TODO resolve: xác thực admin được giao; cập nhật report, ẩn comment nếu duyệt
# và ghi ActionLog trong một transaction; rejected không tự ẩn bình luận.
