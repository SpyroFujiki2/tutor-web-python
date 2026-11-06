"""Model: comment_report. Mẫu: báo cáo một bình luận mà user được phép đọc."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models import CommentReport


def report_comment(
    session: Session, *, reporter_id: UUID, comment_id: UUID, reason_category: str,
    reason_details: str = "",
) -> CommentReport:
    from app.modules.community.community_service import submit_report
    return submit_report(session, reporter_id, comment_id,
                         {"reason_category": reason_category, "reason_details": reason_details})


# TODO submit_details: schema giới hạn reason/category; thêm rate limit và chốt
# chính sách báo cáo trùng trước khi đưa hàm mẫu ra endpoint công khai.
# TODO claim_report: kiểm tra moderator; khóa pending report, gán admin_id và
# locked_at; dùng row lock/skip_locked cho hàng đợi nhiều admin.
# TODO resolve: xác thực admin được giao; cập nhật report, ẩn comment nếu duyệt
# và ghi ActionLog trong một transaction; rejected không tự ẩn bình luận.
