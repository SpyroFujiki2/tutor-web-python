from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"


class UserRole(StrEnum):
    GUEST = "guest"
    MEMBER = "member"
    STUDENT = "student"
    TRAINEE_TUTOR = "trainee_tutor"
    TUTOR = "tutor"
    ADMIN = "admin"
    HEAD_ADMIN = "head_admin"


class ServiceType(StrEnum):
    BOOKING = "booking"
    COURSE = "course"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BookingStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    DISPUTING = "disputing"


class CourseStatus(StrEnum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


class CourseResult(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAILED = "failed"


class DisputeVerdict(StrEnum):
    REFUND_FULL = "refund_full"
    REFUND_PARTIAL = "refund_partial"
    REJECTED = "rejected"


class RequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WalletType(StrEnum):
    NORMAL = "normal"
    COMMERCIAL = "commercial"


class TransactionType(StrEnum):
    RECHARGE = "recharge"
    PAYMENT = "payment"
    REVENUE = "revenue"
    WITHDRAW = "withdraw"
    REFUND = "refund"


class CashOrderType(StrEnum):
    IN = "in"
    OUT = "out"


class CashOrderStatus(StrEnum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class EscrowStatus(StrEnum):
    HELD = "held"
    RELEASED = "released"
    REFUNDED = "refunded"


class BookingSessionStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


def _enum_type(enum_class: type[StrEnum], name: str) -> ENUM:
    # Persist DBML values (including "in"), rather than Python member names.
    return ENUM(enum_class, name=name, values_callable=lambda cls: [item.value for item in cls])


user_status_enum = _enum_type(UserStatus, "user_status")
user_role_enum = _enum_type(UserRole, "user_role")
service_type_enum = _enum_type(ServiceType, "service_type")
subscription_status_enum = _enum_type(SubscriptionStatus, "subscription_status")
booking_status_enum = _enum_type(BookingStatus, "booking_status")
course_status_enum = _enum_type(CourseStatus, "course_status")
course_result_enum = _enum_type(CourseResult, "course_result")
dispute_verdict_enum = _enum_type(DisputeVerdict, "dispute_verdict")
request_status_enum = _enum_type(RequestStatus, "request_status")
wallet_type_enum = _enum_type(WalletType, "wallet_type")
transaction_type_enum = _enum_type(TransactionType, "transaction_type")
cash_order_type_enum = _enum_type(CashOrderType, "cash_order_type")
cash_order_status_enum = _enum_type(CashOrderStatus, "cash_order_status")
escrow_status_enum = _enum_type(EscrowStatus, "escrow_status")
booking_session_status_enum = _enum_type(BookingSessionStatus, "booking_session_status")
