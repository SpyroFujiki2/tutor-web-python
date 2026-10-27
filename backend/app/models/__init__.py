"""Import all mapped tables so Base.metadata is complete for migrations."""

from app.models.base import Base
from app.models.auth_session import AuthSession
from app.models.action_log import ActionLog
from app.models.attendance import Attendance
from app.models.booking import Booking
from app.models.booking_session import BookingSession
from app.models.booking_settlement import BookingSettlement
from app.models.cash_order import CashOrder
from app.models.comment import Comment
from app.models.comment_report import CommentReport
from app.models.course import Course
from app.models.course_progress import CourseProgress
from app.models.credit_package import CreditPackage
from app.models.dispute import Dispute
from app.models.external_transaction import ExternalTransaction
from app.models.internal_transaction import InternalTransaction
from app.models.lesson import Lesson
from app.models.message import Message
from app.models.payment_method import PaymentMethod
from app.models.post import Post
from app.models.role_request import RoleRequest
from app.models.tutoring_package import TutoringPackage
from app.models.user import User
from app.models.user_subscription import UserSubscription
from app.models.wallet import Wallet
from app.models.wallet_snapshot import WalletSnapshot

__all__ = [
    "Base", "AuthSession", "ActionLog", "Attendance", "Booking", "BookingSession", "BookingSettlement",
    "CashOrder", "Comment", "CommentReport", "Course", "CourseProgress", "CreditPackage",
    "Dispute", "ExternalTransaction", "InternalTransaction", "Lesson", "Message",
    "PaymentMethod", "Post", "RoleRequest", "TutoringPackage", "User", "UserSubscription",
    "Wallet", "WalletSnapshot",
]
