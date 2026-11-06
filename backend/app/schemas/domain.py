"""Explicit API inputs; administrative fields never come from public payloads."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.models.enums import CourseStatus, DisputeVerdict, UserStatus, WalletType

Money = Annotated[int, Field(strict=True, ge=0, le=2_147_483_647)]
PositiveMoney = Annotated[int, Field(strict=True, gt=0, le=2_147_483_647)]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
Content = Annotated[str, Field(min_length=1, max_length=20000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Purchase(Input):
    request_id: UUID


class CourseInput(Input):
    title: ShortText
    description: str = Field(default="", max_length=20000)
    price: Money
    is_live: bool = False
    status: CourseStatus = CourseStatus.VISIBLE


class PackageInput(Input):
    name: ShortText
    price: Money
    is_active: bool = True


class CreditPackageInput(PackageInput):
    credits: PositiveMoney
    price: PositiveMoney


class LessonInput(Input):
    order_idx: int = Field(ge=1, le=10000)
    media_url: HttpUrl | None = None
    assignment_url: HttpUrl | None = None
    session_count: int | None = Field(default=None, gt=0, le=1000)
    duration_minutes: int | None = Field(default=None, gt=0, le=10000)


class ReorderInput(Input):
    lesson_ids: list[UUID] = Field(min_length=1, max_length=1000)


class SessionInput(Input):
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    meeting_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def interval(self):
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("Cần cả giờ bắt đầu và kết thúc")
        if self.starts_at is not None:
            if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
                raise ValueError("Thời gian phải kèm múi giờ")
            if self.ends_at <= self.starts_at:
                raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        return self


class BookingInput(Purchase):
    package_id: UUID
    subject: ShortText
    requirements: str = Field(default="", max_length=5000)
    sessions: list[SessionInput] = Field(min_length=1, max_length=100)


class AssignInput(Input):
    tutor_id: UUID


class MessageInput(Input):
    content: str = Field(min_length=1, max_length=5000)


class DisputeInput(Input):
    reason_category: ShortText


class ResolveDisputeInput(Input):
    verdict: DisputeVerdict
    refund_amount: Money = 0
    reason: ShortText


class PostInput(Input):
    title: ShortText
    content: Content
    min_role_level: int = Field(default=0, ge=0, le=6)


class CommentInput(Input):
    content: str = Field(min_length=1, max_length=5000)
    parent_id: UUID | None = None


class ReportInput(DisputeInput):
    reason_details: str = Field(default="", max_length=2000)


class DecisionInput(Input):
    approve: bool
    reason: ShortText


class RoleRequestInput(Input):
    request_note: str = Field(min_length=1, max_length=2000)
    answer_url: HttpUrl | None = None


class PaymentMethodInput(Input):
    bank_name: ShortText
    account_number: str = Field(min_length=4, max_length=40, pattern=r"^[0-9A-Za-z -]+$")
    account_holder_name: ShortText


class DepositInput(Purchase):
    package_id: UUID


class WithdrawalInput(Purchase):
    wallet_type: WalletType = WalletType.NORMAL
    payment_method_id: UUID
    amount: PositiveMoney


class CashDecisionInput(Input):
    success: bool
    reason: ShortText


class StatusInput(Input):
    status: UserStatus
    reason: ShortText


class WalletInput(Input):
    type: WalletType


class AttendanceInput(Input):
    duration_watched: int = Field(ge=0, le=600000)
    completed: bool = False


class GradeInput(Input):
    midterm_score: int = Field(ge=0, le=100)
    endterm_score: int = Field(ge=0, le=100)
    practice_score: int = Field(ge=0, le=100)


class LiveAttendanceInput(Input):
    is_absent: bool


class HiddenInput(Input):
    is_hidden: bool
    reason: ShortText


class CommentEditInput(Input):
    content: str = Field(min_length=1, max_length=5000)


class SessionAction(Input):
    action: Literal["complete", "cancel"]


class ReasonInput(Input):
    reason: ShortText


class CreditTransferInput(Purchase):
    source_type: WalletType
    destination_type: WalletType
    amount: PositiveMoney


class DebtRepaymentInput(Purchase):
    amount: PositiveMoney


class FinancialCorrectionInput(Purchase):
    reason: ShortText


class PlatformFundingInput(DebtRepaymentInput):
    reason: ShortText


class WalletStatusInput(ReasonInput):
    is_active: bool = Field(strict=True)


class WalletContractInput(ReasonInput):
    commission_rate: int = Field(ge=0, le=100, strict=True)
    contract_id: str | None = Field(default=None, max_length=200)
