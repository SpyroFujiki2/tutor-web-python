"""Application API. Authorization lives in services, writes commit exactly once."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import HttpUrl
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.database import get_session
from app.models import (
    Attendance, Booking, BookingSession, BookingSettlement, CashOrder, Comment,
    CommentReport, Course, CourseProgress, CreditPackage, Dispute, ExternalTransaction,
    Lesson, Post, RoleRequest, TutoringPackage, User, UserSubscription, Wallet, WalletSnapshot,
)
from app.models.enums import BookingStatus, CashOrderType, CourseStatus, EscrowStatus, UserRole, WalletType
from app.modules.common import actor, audit, get, now, require
from app.modules.community import community_service as community
from app.modules.community.post import get_readable_post
from app.modules.community.comment import list_visible_comments
from app.modules.finance import payments
from app.modules.finance.wallet import configure_commercial_wallet, set_wallet_status, wallet_summary
from app.modules.finance.cash_order import cancel_cash_order, cash_order_metadata, get_my_cash_order
from app.modules.finance.credit_package import deactivate_credit_package, list_active_credit_packages, save_credit_package
from app.modules.finance.internal_transaction import fund_platform, list_admin_wallet_ledger, move_own_credits, repay_debt, reverse_internal_transaction
from app.modules.finance.external_transaction import reverse_external_transaction
from app.modules.finance.booking_settlement import refund_released_booking, release_settlement
from app.modules.finance.wallet_snapshot import reconcile_wallet
from app.modules.users.payment_method import list_my_payment_methods
from app.modules.learning import learning_service as learning
from app.modules.learning.course_progress import get_my_course_progress
from app.modules.learning.lesson import list_my_course_lessons
from app.modules.tutoring import tutoring_service as tutoring
from app.modules.tutoring.tutoring_package import deactivate_tutoring_package, list_active_tutoring_packages, save_tutoring_package
from app.modules.users import accounts
from app.modules.users.action_log import list_admin_logs
from app.modules.users.user_subscription import expire_subscriptions as expire_subscription_records
from app.schemas import domain as inputs
from app.schemas import responses as out
from app.schemas.auth import CurrentUserResponse

router = APIRouter(tags=["application"])
DB = Annotated[Session, Depends(get_session)]
Current = Annotated[User, Depends(get_current_user)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def administrator(user: Current, session: DB):
    return actor(session, user.id, admin=True)


Admin = Annotated[User, Depends(administrator)]


def data(payload):
    def clean(value):
        if isinstance(value, HttpUrl):
            return str(value)
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items()}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return clean(payload.model_dump())


def saved(session, row, schema):
    session.flush()
    result = schema.model_validate(row, from_attributes=True)
    session.commit()
    return result


def page(session, statement, limit, offset):
    return list(session.scalars(statement.offset(offset).limit(limit)))


def bank_response(row):
    return out.PaymentMethodResponse(id=row.id, bank_name=row.bank_name,
                                    account_number_masked="****" + (row.account_number or "")[-4:],
                                    account_holder_name=row.account_holder_name)


@router.get("/courses", response_model=list[out.CourseResponse])
def courses(session: DB, limit: Limit = 20, offset: Offset = 0, q: str = Query(default="", max_length=200)):
    stmt = select(Course).where(Course.status == CourseStatus.VISIBLE)
    if q:
        stmt = stmt.where(Course.title.contains(q, autoescape=True))
    return page(session, stmt.order_by(Course.created_at.desc(), Course.id), limit, offset)


@router.get("/courses/{course_id}", response_model=out.CourseResponse)
def course_detail(course_id: UUID, session: DB):
    row = get(session, Course, course_id)
    require(row.status == CourseStatus.VISIBLE, "Không tìm thấy khóa học", LookupError)
    return row


@router.post("/courses/{course_id}/purchase", response_model=out.SubscriptionResponse)
def purchase(course_id: UUID, payload: inputs.Purchase, session: DB, user: Current):
    return saved(session, learning.purchase_course(session, user.id, course_id, payload.request_id), out.SubscriptionResponse)


@router.get("/tutoring-packages", response_model=list[out.PackageResponse])
def packages(session: DB, limit: Limit = 20, offset: Offset = 0, q: str = Query(default="", max_length=200)):
    return list_active_tutoring_packages(session, limit=limit, offset=offset, query=q)


@router.get("/credit-packages", response_model=list[out.CreditPackageResponse])
def credit_packages(session: DB, limit: Limit = 20, offset: Offset = 0, q: str = Query(default='', max_length=200)):
    return list_active_credit_packages(session, limit=limit, offset=offset, query=q)


@router.get("/me/subscriptions", response_model=list[out.SubscriptionResponse])
def subscriptions(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(UserSubscription).where(UserSubscription.user_id == user.id)
                .order_by(UserSubscription.activated_at.desc(), UserSubscription.id), limit, offset)


@router.get("/subscriptions/{subscription_id}/lessons", response_model=list[out.LessonResponse])
def lessons(subscription_id: UUID, session: DB, user: Current):
    return list_my_course_lessons(session, subscription_id, user.id)


@router.get("/subscriptions/{subscription_id}/progress", response_model=out.ProgressResponse)
def progress(subscription_id: UUID, session: DB, user: Current):
    return get_my_course_progress(session, subscription_id, user.id)


@router.get("/subscriptions/{subscription_id}/course", response_model=out.CourseResponse)
def subscribed_course(subscription_id: UUID, session: DB, user: Current):
    progress = get_my_course_progress(session, subscription_id, user.id)
    return get(session, Course, progress.course_id)


@router.get("/subscriptions/{subscription_id}/attendance", response_model=list[out.AttendanceResponse])
def attendance(subscription_id: UUID, session: DB, user: Current):
    get_my_course_progress(session, subscription_id, user.id)
    return list(session.scalars(select(Attendance).where(Attendance.subscription_id == subscription_id).order_by(Attendance.lesson_id)))


@router.post("/subscriptions/{subscription_id}/lessons/{lesson_id}/watch", response_model=out.ProgressResponse)
def watch(subscription_id: UUID, lesson_id: UUID, payload: inputs.AttendanceInput, session: DB, user: Current):
    return saved(session, learning.record_attendance(session, user.id, subscription_id, lesson_id,
                 payload.duration_watched, payload.completed), out.ProgressResponse)


@router.get("/bookings", response_model=list[out.BookingResponse])
def bookings(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Booking).where(or_(Booking.customer_id == user.id, Booking.tutor_id == user.id))
                .order_by(Booking.created_at.desc(), Booking.id), limit, offset)


@router.post("/bookings", response_model=out.BookingResponse, status_code=201)
def create_booking(payload: inputs.BookingInput, session: DB, user: Current):
    return saved(session, tutoring.create_booking(session, user.id, data(payload)), out.BookingResponse)


@router.get("/bookings/{booking_id}", response_model=out.BookingResponse)
def booking_detail(booking_id: UUID, session: DB, user: Current):
    return tutoring.accessible_booking(session, user.id, booking_id)


@router.post("/bookings/{booking_id}/pay", response_model=out.BookingResponse)
def pay_booking(booking_id: UUID, session: DB, user: Current):
    return saved(session, tutoring.pay_booking(session, user.id, booking_id), out.BookingResponse)


@router.post("/bookings/{booking_id}/cancel", response_model=out.BookingResponse)
def cancel_booking(booking_id: UUID, session: DB, user: Current):
    return saved(session, tutoring.cancel_booking(session, user.id, booking_id), out.BookingResponse)


@router.post("/bookings/{booking_id}/complete", response_model=out.BookingResponse)
def complete_booking(booking_id: UUID, session: DB, user: Current):
    return saved(session, tutoring.complete_booking(session, user.id, booking_id), out.BookingResponse)


@router.get("/bookings/{booking_id}/sessions", response_model=list[out.SessionResponse])
def booking_sessions(booking_id: UUID, session: DB, user: Current):
    tutoring.accessible_booking(session, user.id, booking_id, administration=True)
    return list(session.scalars(select(BookingSession).where(BookingSession.booking_id == booking_id).order_by(BookingSession.session_no)))


@router.post("/bookings/{booking_id}/sessions", response_model=out.SessionResponse)
def schedule(booking_id: UUID, payload: inputs.SessionInput, session: DB, user: Current):
    return saved(session, tutoring.schedule_session(session, user.id, booking_id, data(payload)), out.SessionResponse)


@router.put("/bookings/{booking_id}/sessions/{session_id}", response_model=out.SessionResponse)
def reschedule(booking_id: UUID, session_id: UUID, payload: inputs.SessionInput, session: DB, user: Current):
    return saved(session, tutoring.schedule_session(session, user.id, booking_id, data(payload), session_id), out.SessionResponse)


@router.post("/bookings/{booking_id}/sessions/{session_id}/action", response_model=out.SessionResponse)
def session_action(booking_id: UUID, session_id: UUID, payload: inputs.SessionAction, session: DB, user: Current):
    return saved(session, tutoring.session_action(session, user.id, booking_id, session_id, payload.action), out.SessionResponse)


@router.get("/bookings/{booking_id}/messages", response_model=list[out.MessageResponse])
def messages(booking_id: UUID, session: DB, user: Current, dispute_id: UUID | None = None,
             limit: Limit = 50, offset: Offset = 0, before_id: int | None = Query(default=None, gt=0)):
    return tutoring.list_messages(session, user.id, booking_id, dispute_id, limit=limit, offset=offset, before_id=before_id)


@router.post("/bookings/{booking_id}/messages", response_model=out.MessageResponse, status_code=201)
def send_message(booking_id: UUID, payload: inputs.MessageInput, session: DB, user: Current, dispute_id: UUID | None = None):
    return saved(session, tutoring.send_message(session, user.id, booking_id, payload.content, dispute_id), out.MessageResponse)


@router.post("/bookings/{booking_id}/dispute", response_model=out.DisputeResponse)
def open_dispute(booking_id: UUID, payload: inputs.DisputeInput, session: DB, user: Current):
    return saved(session, tutoring.open_dispute(session, user.id, booking_id, payload.reason_category), out.DisputeResponse)


@router.get("/disputes", response_model=list[out.DisputeResponse])
def disputes(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Dispute).join(Booking, Booking.id == Dispute.booking_id).where(or_(
        Booking.customer_id == user.id, Booking.tutor_id == user.id, Dispute.admin_id == user.id))
        .order_by(Dispute.created_at.desc(), Dispute.id), limit, offset)


@router.get("/me/wallets", response_model=list[out.WalletResponse])
def wallets(session: DB, user: Current):
    return [wallet_summary(session, row) for row in session.scalars(select(Wallet).where(Wallet.user_id == user.id).order_by(Wallet.type))]


@router.post("/me/wallets", response_model=out.WalletResponse)
def create_wallet(payload: inputs.WalletInput, session: DB, user: Current):
    wallet = accounts.create_wallet(session, user.id, payload.type)
    result = out.WalletResponse.model_validate(wallet_summary(session, wallet))
    session.commit()
    return result


@router.get("/me/wallets/{wallet_type}/history", response_model=list[out.HistoryResponse])
def history(wallet_type: WalletType, session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return payments.wallet_history(session, user.id, wallet_type, limit=limit, offset=offset)


@router.get("/me/wallets/{wallet_type}/external-history", response_model=list[out.ExternalResponse])
def external_history(wallet_type: WalletType, session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    wallet = payments.owned_wallet(session, user.id, wallet_type, require_active=False)
    return page(session, select(ExternalTransaction).where(or_(ExternalTransaction.source_wallet_id == wallet.id,
                ExternalTransaction.destination_wallet_id == wallet.id)).order_by(ExternalTransaction.created_at.desc().nulls_last(), ExternalTransaction.id), limit, offset)


@router.get("/me/wallets/{wallet_type}/snapshots", response_model=list[out.SnapshotResponse])
def snapshots(wallet_type: WalletType, session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    wallet = payments.owned_wallet(session, user.id, wallet_type, require_active=False)
    return page(session, select(WalletSnapshot).where(WalletSnapshot.wallet_id == wallet.id)
                .order_by(WalletSnapshot.snapshot_date.desc().nulls_last(), WalletSnapshot.id), limit, offset)


@router.get("/me/settlements", response_model=list[out.SettlementResponse])
def settlements(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(BookingSettlement).join(Wallet, Wallet.id == BookingSettlement.tutor_wallet_id)
                .where(Wallet.user_id == user.id).order_by(BookingSettlement.created_at.desc(), BookingSettlement.id), limit, offset)


@router.get("/me/payment-methods", response_model=list[out.PaymentMethodResponse])
def payment_methods(session: DB, user: Current, limit: Limit = 50, offset: Offset = 0):
    return [bank_response(row) for row in list_my_payment_methods(session, user.id, limit=limit, offset=offset)]


@router.post("/me/payment-methods", response_model=out.PaymentMethodResponse, status_code=201)
def add_payment_method(payload: inputs.PaymentMethodInput, session: DB, user: Current):
    row = accounts.save_payment_method(session, user.id, data(payload))
    result = bank_response(row)
    session.commit()
    return result


@router.put("/me/payment-methods/{method_id}", response_model=out.PaymentMethodResponse)
def update_payment_method(method_id: UUID, payload: inputs.PaymentMethodInput, session: DB, user: Current):
    row = accounts.save_payment_method(session, user.id, data(payload), method_id)
    result = bank_response(row)
    session.commit()
    return result


@router.delete("/me/payment-methods/{method_id}", status_code=204)
def remove_payment_method(method_id: UUID, session: DB, user: Current):
    accounts.remove_payment_method(session, user.id, method_id)
    session.commit()
    return Response(status_code=204)


@router.get("/me/cash-orders", response_model=list[out.CashOrderResponse])
def cash_orders(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CashOrder).where(CashOrder.user_id == user.id)
                .order_by(CashOrder.created_at.desc(), CashOrder.id), limit, offset)


@router.post("/me/deposits", response_model=out.CashOrderResponse, status_code=201)
def deposit(payload: inputs.DepositInput, session: DB, user: Current):
    return saved(session, payments.create_deposit(session, user.id, payload.request_id, payload.package_id), out.CashOrderResponse)


@router.post("/me/withdrawals", response_model=out.CashOrderResponse, status_code=201)
def withdrawal(payload: inputs.WithdrawalInput, session: DB, user: Current):
    return saved(session, payments.create_withdrawal(session, user.id, payload.request_id,
                 payload.wallet_type, payload.payment_method_id, payload.amount), out.CashOrderResponse)


@router.get("/posts", response_model=list[out.PostResponse])
def posts(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0,
          q: str = Query(default="", max_length=200), before_id: UUID | None = None):
    return community.list_posts(session, user.id, limit=limit, offset=offset, query=q, before_id=before_id)


@router.post("/posts", response_model=out.PostResponse, status_code=201)
def create_post(payload: inputs.PostInput, session: DB, user: Current):
    return saved(session, community.save_post(session, user.id, data(payload)), out.PostResponse)


@router.get("/posts/{post_id}", response_model=out.PostResponse)
def post_detail(post_id: UUID, session: DB, user: Current):
    return get_readable_post(session, post_id, user.id)


@router.put("/posts/{post_id}", response_model=out.PostResponse)
def update_post(post_id: UUID, payload: inputs.PostInput, session: DB, user: Current):
    return saved(session, community.save_post(session, user.id, data(payload), post_id), out.PostResponse)


@router.post("/posts/{post_id}/visibility", response_model=out.PostResponse)
def post_visibility(post_id: UUID, payload: inputs.HiddenInput, session: DB, user: Current):
    return saved(session, community.hide_content(session, user.id, Post, post_id, payload.is_hidden, payload.reason), out.PostResponse)


@router.get("/posts/{post_id}/comments", response_model=list[out.CommentResponse])
def comments(post_id: UUID, session: DB, user: Current, limit: Limit = 50, offset: Offset = 0,
             after_id: UUID | None = None):
    return list_visible_comments(session, post_id, user.id, limit=limit, offset=offset, after_id=after_id)


@router.post("/posts/{post_id}/comments", response_model=out.CommentResponse, status_code=201)
def create_comment(post_id: UUID, payload: inputs.CommentInput, session: DB, user: Current):
    return saved(session, community.create_comment(session, user.id, post_id, payload.content, payload.parent_id), out.CommentResponse)


@router.put("/comments/{comment_id}", response_model=out.CommentResponse)
def edit_comment(comment_id: UUID, payload: inputs.CommentEditInput, session: DB, user: Current):
    return saved(session, community.edit_comment(session, user.id, comment_id, payload.content), out.CommentResponse)


@router.post("/comments/{comment_id}/visibility", response_model=out.CommentResponse)
def comment_visibility(comment_id: UUID, payload: inputs.HiddenInput, session: DB, user: Current):
    return saved(session, community.hide_content(session, user.id, Comment, comment_id, payload.is_hidden, payload.reason), out.CommentResponse)


@router.post("/comments/{comment_id}/reports", response_model=out.ReportResponse, status_code=201)
def report(comment_id: UUID, payload: inputs.ReportInput, session: DB, user: Current):
    return saved(session, community.submit_report(session, user.id, comment_id, data(payload)), out.ReportResponse)


@router.get("/me/reports", response_model=list[out.ReportResponse])
def my_reports(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CommentReport).where(CommentReport.reporter_id == user.id)
                .order_by(CommentReport.created_at.desc(), CommentReport.id), limit, offset)


@router.get("/me/role-requests", response_model=list[out.RoleRequestResponse])
def role_requests(session: DB, user: Current, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(RoleRequest).where(RoleRequest.user_id == user.id)
                .order_by(RoleRequest.created_at.desc(), RoleRequest.id), limit, offset)


@router.post("/me/role-requests", response_model=out.RoleRequestResponse, status_code=201)
def submit_role_request(payload: inputs.RoleRequestInput, session: DB, user: Current):
    return saved(session, community.submit_role_request(session, user.id, data(payload)), out.RoleRequestResponse)


@router.get("/admin/courses", response_model=list[out.CourseResponse])
def admin_courses(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Course).order_by(Course.created_at.desc(), Course.id), limit, offset)


@router.post("/admin/courses", response_model=out.CourseResponse, status_code=201)
def create_course(payload: inputs.CourseInput, session: DB, admin: Admin):
    return saved(session, learning.save_course(session, admin.id, data(payload)), out.CourseResponse)


@router.put("/admin/courses/{course_id}", response_model=out.CourseResponse)
def update_course(course_id: UUID, payload: inputs.CourseInput, session: DB, admin: Admin):
    return saved(session, learning.save_course(session, admin.id, data(payload), course_id), out.CourseResponse)


@router.get("/admin/courses/{course_id}/lessons", response_model=list[out.LessonResponse])
def admin_lessons(course_id: UUID, session: DB, admin: Admin):
    get(session, Course, course_id)
    return list(session.scalars(select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.order_idx)))


@router.post("/admin/courses/{course_id}/lessons", response_model=out.LessonResponse, status_code=201)
def create_lesson(course_id: UUID, payload: inputs.LessonInput, session: DB, admin: Admin):
    return saved(session, learning.save_lesson(session, admin.id, course_id, data(payload)), out.LessonResponse)


@router.put("/admin/courses/{course_id}/lessons/{lesson_id}", response_model=out.LessonResponse)
def update_lesson(course_id: UUID, lesson_id: UUID, payload: inputs.LessonInput, session: DB, admin: Admin):
    return saved(session, learning.save_lesson(session, admin.id, course_id, data(payload), lesson_id), out.LessonResponse)


@router.delete("/admin/courses/{course_id}/lessons/{lesson_id}", status_code=204)
def remove_lesson(course_id: UUID, lesson_id: UUID, session: DB, admin: Admin):
    learning.remove_lesson(session, admin.id, course_id, lesson_id)
    session.commit()
    return Response(status_code=204)


@router.post("/admin/courses/{course_id}/reorder", response_model=list[out.LessonResponse])
def reorder(course_id: UUID, payload: inputs.ReorderInput, session: DB, admin: Admin):
    rows = learning.reorder_lessons(session, admin.id, course_id, payload.lesson_ids)
    session.flush()
    result = [out.LessonResponse.model_validate(row) for row in rows]
    session.commit()
    return result




@router.get("/admin/tutoring-packages", response_model=list[out.PackageResponse])
def admin_packages(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(TutoringPackage).order_by(TutoringPackage.id), limit, offset)


@router.post("/admin/tutoring-packages", response_model=out.PackageResponse, status_code=201)
def create_package(payload: inputs.PackageInput, session: DB, admin: Admin):
    return saved(session, save_tutoring_package(session, admin.id, data(payload)), out.PackageResponse)


@router.put("/admin/tutoring-packages/{package_id}", response_model=out.PackageResponse)
def update_package(package_id: UUID, payload: inputs.PackageInput, session: DB, admin: Admin):
    return saved(session, save_tutoring_package(session, admin.id, data(payload), package_id), out.PackageResponse)


@router.post("/admin/tutoring-packages/{package_id}/deactivate", response_model=out.PackageResponse)
def deactivate_package(package_id: UUID, session: DB, admin: Admin):
    return saved(session, deactivate_tutoring_package(session, admin.id, package_id), out.PackageResponse)


@router.get("/admin/credit-packages", response_model=list[out.CreditPackageResponse])
def admin_credit_packages(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CreditPackage).order_by(CreditPackage.id), limit, offset)


@router.post("/admin/credit-packages", response_model=out.CreditPackageResponse, status_code=201)
def create_credit_package(payload: inputs.CreditPackageInput, session: DB, admin: Admin):
    return saved(session, save_credit_package(session, admin.id, data(payload)), out.CreditPackageResponse)


@router.put("/admin/credit-packages/{package_id}", response_model=out.CreditPackageResponse)
def update_credit_package(package_id: UUID, payload: inputs.CreditPackageInput, session: DB, admin: Admin):
    return saved(session, save_credit_package(session, admin.id, data(payload), package_id), out.CreditPackageResponse)


@router.get("/admin/users", response_model=list[CurrentUserResponse])
def users(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0, role: UserRole | None = None):
    stmt = select(User).where(User.id != payments.PLATFORM_USER_ID)
    if role:
        stmt = stmt.where(User.role == role)
    return page(session, stmt.order_by(User.created_at.desc(), User.id), limit, offset)


@router.post("/admin/users/{user_id}/status", response_model=CurrentUserResponse)
def user_status(user_id: UUID, payload: inputs.StatusInput, session: DB, admin: Admin):
    require(user_id != payments.PLATFORM_USER_ID, "Không sửa tài khoản hệ thống", PermissionError)
    return saved(session, accounts.change_status(session, admin.id, user_id, payload.status, payload.reason), CurrentUserResponse)


@router.get("/admin/bookings", response_model=list[out.BookingResponse])
def admin_bookings(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Booking).order_by(Booking.created_at.desc(), Booking.id), limit, offset)


@router.post("/admin/bookings/{booking_id}/assign", response_model=out.BookingResponse)
def assign(booking_id: UUID, payload: inputs.AssignInput, session: DB, admin: Admin):
    return saved(session, tutoring.assign_tutor(session, admin.id, booking_id, payload.tutor_id), out.BookingResponse)


@router.get("/admin/cash-orders", response_model=list[out.CashOrderResponse])
def admin_cash_orders(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CashOrder).order_by(CashOrder.created_at.desc(), CashOrder.id), limit, offset)


@router.get("/admin/cash-orders/{order_id}/bank-details", response_model=inputs.PaymentMethodInput)
def withdrawal_bank_details(order_id: UUID, session: DB, admin: Admin):
    require(admin.role == UserRole.HEAD_ADMIN, "Cần quản trị cấp cao", PermissionError)
    row = get(session, CashOrder, order_id)
    require(row.order_type == CashOrderType.OUT, "Đơn không có tài khoản ngân hàng", LookupError)
    metadata = cash_order_metadata(row)
    require(all(metadata.get(key) for key in ('bank_name', 'account_number', 'account_holder_name')),
            'Thông tin tài khoản snapshot chưa đầy đủ')
    audit(session, admin, row, "cash.view_bank_details")
    result = inputs.PaymentMethodInput(**{key: metadata[key] for key in ("bank_name", "account_number", "account_holder_name")})
    session.commit()
    return result


@router.post("/admin/cash-orders/{order_id}/decision", response_model=out.CashOrderResponse)
def cash_decision(order_id: UUID, payload: inputs.CashDecisionInput, session: DB, admin: Admin):
    return saved(session, payments.decide_cash_order(session, admin.id, order_id, payload.success, payload.reason), out.CashOrderResponse)


@router.get("/admin/role-requests", response_model=list[out.RoleRequestResponse])
def admin_role_requests(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(RoleRequest).order_by(RoleRequest.created_at.desc(), RoleRequest.id), limit, offset)


@router.post("/admin/role-requests/{request_id}/decision", response_model=out.RoleRequestResponse)
def role_decision(request_id: UUID, payload: inputs.DecisionInput, session: DB, admin: Admin):
    return saved(session, community.decide_role_request(session, admin.id, request_id, payload.approve, payload.reason), out.RoleRequestResponse)


@router.get("/admin/reports", response_model=list[out.ReportResponse])
def admin_reports(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CommentReport).order_by(CommentReport.created_at.desc(), CommentReport.id), limit, offset)


@router.post("/admin/reports/{report_id}/claim", response_model=out.ReportResponse)
def report_claim(report_id: UUID, session: DB, admin: Admin):
    return saved(session, community.claim_report(session, admin.id, report_id), out.ReportResponse)


@router.post("/admin/reports/{report_id}/decision", response_model=out.ReportResponse)
def report_decision(report_id: UUID, payload: inputs.DecisionInput, session: DB, admin: Admin):
    return saved(session, community.resolve_report(session, admin.id, report_id, payload.approve, payload.reason), out.ReportResponse)


@router.get("/admin/reports/{report_id}/context", response_model=out.ReportContextResponse)
def report_context(report_id: UUID, session: DB, admin: Admin):
    report = get(session, CommentReport, report_id)
    require(report.admin_id == admin.id, "Báo cáo chưa giao cho bạn", PermissionError)
    comment = get(session, Comment, report.target_id)
    return {"comment": comment, "post": get(session, Post, comment.post_id)}


@router.get("/admin/posts", response_model=list[out.PostResponse])
def admin_posts(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Post).order_by(Post.created_at.desc(), Post.id), limit, offset)


@router.get("/admin/disputes", response_model=list[out.DisputeResponse])
def admin_disputes(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(Dispute).order_by(Dispute.created_at.desc(), Dispute.id), limit, offset)


@router.post("/admin/disputes/{dispute_id}/claim", response_model=out.DisputeResponse)
def dispute_claim(dispute_id: UUID, session: DB, admin: Admin):
    return saved(session, tutoring.claim_dispute(session, admin.id, dispute_id), out.DisputeResponse)


@router.post("/admin/disputes/{dispute_id}/decision", response_model=out.DisputeResponse)
def dispute_decision(dispute_id: UUID, payload: inputs.ResolveDisputeInput, session: DB, admin: Admin):
    return saved(session, tutoring.resolve_dispute(session, admin.id, dispute_id, payload.verdict,
                 payload.refund_amount, payload.reason), out.DisputeResponse)


@router.get("/admin/settlements", response_model=list[out.SettlementResponse])
def admin_settlements(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(BookingSettlement).order_by(BookingSettlement.created_at.desc(), BookingSettlement.id), limit, offset)


@router.post("/admin/settlements/{settlement_id}/release", response_model=out.SettlementResponse)
def release(settlement_id: UUID, session: DB, admin: Admin):
    return saved(session, tutoring.release_settlement(session, admin.id, settlement_id), out.SettlementResponse)


@router.get("/admin/progress", response_model=list[out.ProgressResponse])
def admin_progress(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return page(session, select(CourseProgress).order_by(CourseProgress.updated_at.desc(), CourseProgress.subscription_id), limit, offset)


@router.post("/admin/subscriptions/{subscription_id}/grade", response_model=out.ProgressResponse)
def grade(subscription_id: UUID, payload: inputs.GradeInput, session: DB, admin: Admin):
    return saved(session, learning.grade_course(session, admin.id, subscription_id, data(payload)), out.ProgressResponse)


@router.post("/admin/subscriptions/{subscription_id}/refund", response_model=out.SubscriptionResponse)
def refund_course(subscription_id: UUID, payload: inputs.ReasonInput, session: DB, admin: Admin):
    return saved(session, learning.refund_course(session, admin.id, subscription_id, payload.reason), out.SubscriptionResponse)


@router.post("/admin/subscriptions/{subscription_id}/lessons/{lesson_id}/attendance", response_model=out.ProgressResponse)
def record_live_attendance(subscription_id: UUID, lesson_id: UUID, payload: inputs.LiveAttendanceInput, session: DB, admin: Admin):
    return saved(session, learning.live_attendance(session, admin.id, subscription_id, lesson_id, payload.is_absent), out.ProgressResponse)


@router.get("/admin/action-logs", response_model=list[out.LogResponse])
def logs(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0,
         target_id: UUID | None = None, target_user_id: UUID | None = None):
    return list_admin_logs(session, admin.id, limit=limit, offset=offset, target_id=target_id, target_user_id=target_user_id)


@router.post("/admin/jobs/snapshots", response_model=list[out.SnapshotResponse])
def snapshot_job(session: DB, admin: Admin, limit: Limit = 100, offset: Offset = 0):
    result = [out.SnapshotResponse.model_validate(row) for row in payments.daily_snapshots(session, admin.id, limit=limit, offset=offset)]
    session.commit()
    return result


@router.post("/admin/jobs/expire-subscriptions")
def expire_subscriptions(session: DB, admin: Admin):
    count = expire_subscription_records(session, admin.id)
    session.commit()
    return {"updated": count}


@router.get('/me/cash-orders/{order_id}', response_model=out.CashOrderResponse)
def cash_order_detail(order_id: UUID, session: DB, user: Current):
    return get_my_cash_order(session, order_id, user.id)


@router.post('/me/cash-orders/{order_id}/cancel', response_model=out.CashOrderResponse)
def cancel_pending_cash_order(order_id: UUID, session: DB, user: Current):
    return saved(session, cancel_cash_order(session, user.id, order_id), out.CashOrderResponse)


@router.post('/me/transfers', response_model=out.TransferResponse)
def own_wallet_transfer(payload: inputs.CreditTransferInput, session: DB, user: Current):
    return saved(session, move_own_credits(session, user.id, payload.request_id,
                 payload.source_type, payload.destination_type, payload.amount), out.TransferResponse)


@router.post('/me/debt-repayments', response_model=out.TransferResponse)
def debt_repayment(payload: inputs.DebtRepaymentInput, session: DB, user: Current):
    return saved(session, repay_debt(session, user.id, payload.request_id, payload.amount), out.TransferResponse)


@router.get('/admin/wallets', response_model=list[out.WalletResponse])
def admin_wallets(session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return [wallet_summary(session, row) for row in page(session,
        select(Wallet).where(Wallet.id != payments.PLATFORM_WALLET_ID).order_by(Wallet.created_at.desc(), Wallet.id), limit, offset)]


@router.post('/admin/wallets/{wallet_id}/status', response_model=out.WalletResponse)
def wallet_status(wallet_id: UUID, payload: inputs.WalletStatusInput, session: DB, admin: Admin):
    row = set_wallet_status(session, admin.id, wallet_id, payload.is_active, payload.reason)
    result = out.WalletResponse.model_validate(wallet_summary(session, row))
    session.commit()
    return result


@router.post('/admin/wallets/{wallet_id}/contract', response_model=out.WalletResponse)
def wallet_contract(wallet_id: UUID, payload: inputs.WalletContractInput, session: DB, admin: Admin):
    row = configure_commercial_wallet(session, admin.id, wallet_id, payload.commission_rate, payload.contract_id, payload.reason)
    result = out.WalletResponse.model_validate(wallet_summary(session, row))
    session.commit()
    return result


@router.get('/admin/wallets/{wallet_id}/reconciliation', response_model=out.ReconciliationResponse)
def wallet_reconciliation(wallet_id: UUID, session: DB, admin: Admin):
    return reconcile_wallet(session, admin.id, wallet_id)


@router.get('/admin/wallets/{wallet_id}/ledger', response_model=list[out.FinanceLedgerResponse])
def wallet_admin_ledger(wallet_id: UUID, session: DB, admin: Admin, limit: Limit = 20, offset: Offset = 0):
    return list_admin_wallet_ledger(session, admin.id, wallet_id, limit=limit, offset=offset)


@router.get('/admin/finance/treasury', response_model=out.WalletResponse)
def treasury(session: DB, admin: Admin):
    return wallet_summary(session, get(session, Wallet, payments.PLATFORM_WALLET_ID))


@router.post('/admin/finance/treasury/fund', response_model=out.TransferResponse)
def treasury_funding(payload: inputs.PlatformFundingInput, session: DB, admin: Admin):
    return saved(session, fund_platform(session, admin.id, payload.request_id, payload.amount, payload.reason), out.TransferResponse)


@router.post('/admin/internal-transactions/{transaction_id}/reverse', response_model=out.TransferResponse)
def reverse_internal(transaction_id: UUID, payload: inputs.FinancialCorrectionInput, session: DB, admin: Admin):
    return saved(session, reverse_internal_transaction(session, admin.id, transaction_id, payload.request_id, payload.reason), out.TransferResponse)


@router.post('/admin/external-transactions/{transaction_id}/reverse', response_model=out.ExternalResponse)
def reverse_external(transaction_id: UUID, payload: inputs.FinancialCorrectionInput, session: DB, admin: Admin):
    return saved(session, reverse_external_transaction(session, admin.id, transaction_id, payload.request_id, payload.reason), out.ExternalResponse)


@router.post('/admin/bookings/{booking_id}/refund-released', response_model=out.SettlementResponse)
def late_booking_refund(booking_id: UUID, payload: inputs.ReasonInput, session: DB, admin: Admin):
    return saved(session, refund_released_booking(session, admin.id, booking_id, payload.reason), out.SettlementResponse)


@router.post('/admin/credit-packages/{package_id}/deactivate', response_model=out.CreditPackageResponse)
def deactivate_credit(package_id: UUID, session: DB, admin: Admin):
    return saved(session, deactivate_credit_package(session, admin.id, package_id), out.CreditPackageResponse)


@router.post('/admin/jobs/release-settlements')
def release_due_settlements(request: Request, session: DB, admin: Admin, limit: Limit = 20):
    identities = list(session.scalars(select(BookingSettlement.id).join(Booking, Booking.id == BookingSettlement.booking_id)
        .where(BookingSettlement.status == EscrowStatus.HELD, BookingSettlement.release_date <= now(),
               Booking.status == BookingStatus.COMPLETED).order_by(BookingSettlement.release_date, BookingSettlement.id).limit(limit)))
    admin_id = admin.id
    session.commit()
    released, skipped = [], []
    # Each item is its own caller-owned transaction; no wallet lock crosses items.
    for identity in identities:
        try:
            with request.app.state.session_factory.begin() as job_session:
                release_settlement(job_session, admin_id, identity)
            released.append(str(identity))
        except (ValueError, LookupError, PermissionError) as error:
            skipped.append({'settlement_id': str(identity), 'detail': str(error)})
    return {'released': released, 'skipped': skipped}
