"""Response allowlists, bound to the types in the supplied SQLAlchemy schema.

Only explicitly listed fields can cross the API boundary. Passwords, bank account
numbers and counterparty balances are deliberately absent from these contracts.
"""

from datetime import date, datetime
from typing import Literal, get_args, get_type_hints
from uuid import UUID

from pydantic import BaseModel, ConfigDict, create_model, model_validator

from app import models


def response(name, model, fields):
    hints = get_type_hints(model)
    definitions = {field: (get_args(hints[field])[0], ...) for field in fields.split()}
    return create_model(name, __config__=ConfigDict(from_attributes=True), **definitions)


CourseResponse = response("CourseResponse", models.Course, "id title description price is_live status created_at updated_at")
LessonResponse = response("LessonResponse", models.Lesson, "id course_id order_idx media_url assignment_url session_count duration_minutes duration_seconds")
PackageResponse = response("PackageResponse", models.TutoringPackage, "id name price is_active")
CreditPackageResponse = response("CreditPackageResponse", models.CreditPackage, "id name credits price is_active")
SubscriptionResponse = response("SubscriptionResponse", models.UserSubscription,
                                "id user_id type title_at_purchase price_at_purchase status activated_at expired_at")
ProgressResponse = response("ProgressResponse", models.CourseProgress,
                            "subscription_id course_id progress_percent attendance_ratio midterm_score endterm_score practice_score final_score result completed_at updated_at")
AttendanceResponse = response("AttendanceResponse", models.Attendance, "subscription_id course_id lesson_id is_absent duration_watched")
BookingResponse = response("BookingResponse", models.Booking,
                           "id package_id customer_id tutor_id subscription_id subject requirements status created_at last_updated")
SessionResponse = response("SessionResponse", models.BookingSession,
                           "id booking_id session_no starts_at ends_at meeting_url location note status created_at updated_at")
MessageResponse = response("MessageResponse", models.Message, "id booking_id dispute_id sender_id content file_url created_at")
DisputeResponse = response("DisputeResponse", models.Dispute,
                           "id booking_id raised_by_user_id admin_id reason_category is_completed verdict created_at resolve_at")
PostResponse = response("PostResponse", models.Post,
                        "id author_id author_nickname author_avatar_url title content min_role_level is_hidden created_at")
CommentResponse = response("CommentResponse", models.Comment, "id post_id user_id parent_id content is_hidden created_at")
ReportResponse = response("ReportResponse", models.CommentReport,
                          "id reporter_id target_id reason_category reason_details priority admin_id status created_at locked_at")
RoleRequestResponse = response("RoleRequestResponse", models.RoleRequest,
                               "id user_id current_role_at_request question_set answer_url request_note status priority admin_id admin_note created_at updated_at")
_WalletFields = response("WalletFields", models.Wallet,
                         "id user_id type available_balance holding_balance debt commission_rate contract_id is_active created_at updated_at")


class WalletResponse(_WalletFields):
    reserved_withdrawals: int
    spendable_balance: int

_cash_fields = "id user_id wallet_id order_type package_id amount_vnd credit_amount status created_at updated_at"
_CashOrderFields = response("CashOrderFields", models.CashOrder, _cash_fields)


class CashOrderResponse(_CashOrderFields):
    provider: Literal['manual', 'vnpay'] = 'manual'
    payment_expires_at: datetime | None = None
    cancelled_by_user: bool = False

    @model_validator(mode='before')
    @classmethod
    def include_provider(cls, value):
        if isinstance(value, models.CashOrder):
            metadata = value.bank_info if isinstance(value.bank_info, dict) else {}
            return {**{name: getattr(value, name) for name in _cash_fields.split()},
                    'provider': 'vnpay' if metadata.get('provider') == 'vnpay' else 'manual',
                    'cancelled_by_user': bool(metadata.get('cancelled_by_user')),
                    'payment_expires_at': metadata.get('expires_at') if metadata.get('provider') == 'vnpay' else None}
        return value
SettlementResponse = response("SettlementResponse", models.BookingSettlement,
                              "id booking_id tutor_wallet_id total_amount commission_rate platform_fee tutor_income available_amount hold_amount status release_date actual_released_at created_at")
SnapshotResponse = response("SnapshotResponse", models.WalletSnapshot, "id wallet_id snapshot_date balance_snap holding_snap available_snap")
LogResponse = response("LogResponse", models.ActionLog,
                       "id admin_id target_user_id target_type target_id action_code old_value new_value reason created_at")
ExternalResponse = response("ExternalResponse", models.ExternalTransaction,
                            "id amount cash_order_id balance_before balance_after created_at")


class PaymentMethodResponse(BaseModel):
    id: UUID
    bank_name: str | None
    account_number_masked: str
    account_holder_name: str | None


class HistoryResponse(BaseModel):
    id: UUID
    type: str | None
    amount: int | None
    created_at: datetime | None
    direction: str


class ReportContextResponse(BaseModel):
    comment: CommentResponse
    post: PostResponse


TransferResponse = response('TransferResponse', models.InternalTransaction,
    'id source_wallet_id destination_wallet_id amount type created_at')


class ReconciliationIssue(BaseModel):
    code: str
    transaction_id: UUID | None


class ReconciliationResponse(BaseModel):
    wallet_id: UUID
    status: Literal['ok', 'mismatch']
    baseline_source: Literal['recorded', 'derived', 'missing']
    available_balance: int
    expected_available_balance: int | None
    holding_balance: int
    expected_holding_balance: int
    debt: int
    expected_debt: int | None
    internal_count: int
    external_count: int
    issues: list[ReconciliationIssue]
    warnings: list[str]
    latest_snapshot_date: date | None


class FinanceLedgerResponse(BaseModel):
    id: UUID
    category: Literal['internal', 'external']
    type: str | None
    amount: int | None
    direction: Literal['in', 'out']
    balance_before: int | None
    balance_after: int | None
    created_at: datetime | None
    reversible: bool
