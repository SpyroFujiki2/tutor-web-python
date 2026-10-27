"""Exercise access boundaries and transactions without an external DB server.

SQLite fixtures adapt JSONB, BIGSERIAL and now() DDL on a metadata COPY only.
They do not validate PostgreSQL locking, native enums or production migrations.
"""

import unittest
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DefaultClause, Integer, JSON, MetaData, create_engine, event, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.models import (
    ActionLog, Base, Booking, BookingSession, CashOrder, Comment, CommentReport,
    Course, CourseProgress, InternalTransaction, Lesson, Message, Post,
    TutoringPackage, User, UserSubscription, Wallet,
)
from app.models.enums import (
    BookingSessionStatus, BookingStatus, CashOrderStatus, CashOrderType,
    CourseStatus, ServiceType, SubscriptionStatus, TransactionType, UserRole,
    UserStatus, WalletType,
)
from app.modules.community.comment import list_visible_comments
from app.modules.community.comment_report import report_comment
from app.modules.finance.cash_order import get_my_cash_order
from app.modules.finance.internal_transaction import list_my_internal_transactions
from app.modules.learning.course import list_visible_courses
from app.modules.learning.lesson import list_my_course_lessons
from app.modules.tutoring.booking_session import list_booking_sessions
from app.modules.tutoring.message import send_booking_message
from app.modules.users.action_log import record_admin_action
from app.modules.users.user_subscription import list_my_active_subscriptions


class ModuleFeatureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _record):
            connection.execute("PRAGMA foreign_keys=ON")

        metadata = MetaData()
        for table in Base.metadata.sorted_tables:
            table.to_metadata(metadata)
        for table in metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
                if column.server_default is not None and str(column.server_default.arg) == "now()":
                    column.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))
        metadata.tables["messages"].c.id.type = Integer()
        metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        now = datetime.now(UTC).replace(tzinfo=None)
        self.customer, self.tutor, self.other, self.admin = [uuid4() for _ in range(4)]
        self.package, self.booking, self.course, self.hidden_course = [uuid4() for _ in range(4)]
        self.subscription, self.expired_subscription, self.hidden_subscription = [uuid4() for _ in range(3)]
        self.post, self.comment, self.wallet, self.other_wallet, self.cash_order = [uuid4() for _ in range(5)]
        with self.session.begin():
            self.session.add_all([
                User(id=user_id, role=role, status=UserStatus.ACTIVE)
                for user_id, role in (
                    (self.customer, UserRole.STUDENT), (self.tutor, UserRole.TUTOR),
                    (self.other, UserRole.STUDENT), (self.admin, UserRole.ADMIN),
                )
            ])
            self.session.add(TutoringPackage(id=self.package, name="Sample", price=100, is_active=True))
            self.session.add_all([
                Course(id=self.course, status=CourseStatus.VISIBLE, created_at=now, updated_at=now),
                Course(id=self.hidden_course, status=CourseStatus.HIDDEN, created_at=now, updated_at=now),
            ])
            self.session.flush()
            self.session.add_all([
                UserSubscription(
                    id=subscription_id, user_id=self.customer, type=ServiceType.COURSE,
                    status=SubscriptionStatus.ACTIVE, activated_at=now - timedelta(days=2),
                    expired_at=expires,
                )
                for subscription_id, expires in (
                    (self.subscription, now + timedelta(days=10)),
                    (self.expired_subscription, now - timedelta(days=1)),
                    (self.hidden_subscription, None),
                )
            ])
            self.session.add_all([
                Wallet(id=wallet_id, user_id=user_id, type=WalletType.NORMAL, is_active=True)
                for wallet_id, user_id in ((self.wallet, self.customer), (self.other_wallet, self.other))
            ])
            self.session.add(Post(
                id=self.post, author_id=self.tutor, min_role_level=2, is_hidden=False, created_at=now,
            ))
            self.session.flush()
            self.session.add(Booking(
                id=self.booking, package_id=self.package, customer_id=self.customer,
                tutor_id=self.tutor, status=BookingStatus.ASSIGNED, subject="Original",
            ))
            self.session.add(Comment(
                id=self.comment, post_id=self.post, user_id=self.tutor,
                content="Sample comment", is_hidden=False, created_at=now,
            ))
            for subscription_id, course_id in (
                (self.subscription, self.course), (self.expired_subscription, self.course),
                (self.hidden_subscription, self.hidden_course),
            ):
                self.session.add(CourseProgress(
                    subscription_id=subscription_id, course_id=course_id,
                    progress_percent=Decimal("0"), updated_at=now,
                ))
            for course_id in (self.course, self.hidden_course):
                self.session.add(Lesson(id=uuid4(), course_id=course_id, order_idx=1, media_url="private"))
            self.session.add(CashOrder(
                id=self.cash_order, user_id=self.customer, wallet_id=self.wallet,
                order_type=CashOrderType.IN, status=CashOrderStatus.PENDING,
            ))
            self.session.add_all([
                InternalTransaction(
                    id=uuid4(), source_wallet_id=source, destination_wallet_id=destination,
                    amount=10, type=TransactionType.PAYMENT,
                    source_balance_before=100, source_balance_after=90,
                    destination_balance_before=42, destination_balance_after=52, created_at=now,
                )
                for source, destination in (
                    (self.wallet, self.other_wallet), (self.other_wallet, self.other_wallet),
                )
            ])
            self.session.flush()
            self.session.add(BookingSession(
                id=uuid4(), booking_id=self.booking, session_no=1,
                status=BookingSessionStatus.SCHEDULED, created_at=now, updated_at=now,
            ))

    def test_booking_data_and_messages_are_scoped_to_participants(self):
        with self.session.begin():
            self.assertEqual(len(list_booking_sessions(self.session, self.booking, self.customer)), 1)
            for outsider in (self.other, self.admin):
                with self.subTest(user=outsider), self.assertRaises(LookupError):
                    list_booking_sessions(self.session, self.booking, outsider)
                with self.assertRaises(LookupError):
                    send_booking_message(
                        self.session, booking_id=self.booking, sender_id=outsider, content="Denied",
                    )
            self.assertEqual(self.session.scalar(select(func.count()).select_from(Message)), 0)

    def test_text_message_is_trimmed_and_requires_nonblank_content(self):
        with self.session.begin():
            with self.assertRaises(ValueError):
                send_booking_message(
                    self.session, booking_id=self.booking, sender_id=self.customer, content="  ",
                )
            message = send_booking_message(
                self.session, booking_id=self.booking, sender_id=self.customer, content="  Hello  ",
            )
            self.assertEqual(message.content, "Hello")
            self.assertIsNone(message.dispute_id)
            self.assertIsNotNone(message.id)

    def test_caller_rollback_reverts_flushed_message_and_other_changes(self):
        with self.assertRaisesRegex(RuntimeError, "abort workflow"):
            with self.session.begin():
                self.session.get(Booking, self.booking).subject = "Changed"
                send_booking_message(
                    self.session, booking_id=self.booking, sender_id=self.customer, content="Pending",
                )
                raise RuntimeError("abort workflow")
        with self.session.begin():
            self.assertEqual(self.session.get(Booking, self.booking).subject, "Original")
            self.assertEqual(self.session.scalar(select(func.count()).select_from(Message)), 0)

    def test_paid_hidden_course_remains_accessible_but_expired_or_other_users_are_denied(self):
        with self.session.begin():
            self.assertEqual([course.id for course in list_visible_courses(self.session)], [self.course])
            self.assertEqual(len(list_my_course_lessons(
                self.session, self.hidden_subscription, self.customer,
            )), 1)
            with self.assertRaises(PermissionError):
                list_my_course_lessons(self.session, self.expired_subscription, self.customer)
            with self.assertRaises(LookupError):
                list_my_course_lessons(self.session, self.subscription, self.other)

    def test_active_subscriptions_check_expiry_even_if_status_was_not_updated_by_a_job(self):
        with self.session.begin():
            subscriptions = list_my_active_subscriptions(self.session, self.customer)
            self.assertEqual({row.id for row in subscriptions}, {self.subscription, self.hidden_subscription})

    def test_post_permissions_also_apply_to_comments_and_reports(self):
        with self.session.begin():
            with self.assertRaises(PermissionError):
                list_visible_comments(self.session, self.post)
            self.assertEqual(len(list_visible_comments(self.session, self.post, self.customer)), 1)
            self.session.get(User, self.other).role = UserRole.MEMBER
            with self.assertRaises(PermissionError):
                report_comment(
                    self.session, reporter_id=self.other, comment_id=self.comment, reason_category="spam",
                )
            report = report_comment(
                self.session, reporter_id=self.customer, comment_id=self.comment, reason_category="spam",
            )
            self.assertEqual(report.reporter_id, self.customer)
            self.assertEqual(self.session.scalar(select(func.count()).select_from(CommentReport)), 1)

    def test_wallet_history_does_not_leak_counterparty_balances_or_unrelated_transactions(self):
        with self.session.begin():
            rows = list_my_internal_transactions(self.session, self.customer, WalletType.NORMAL)
            self.assertEqual(len(rows), 1)
            self.assertEqual(set(rows[0]), {"id", "type", "amount", "created_at"})
            with self.assertRaises(LookupError):
                get_my_cash_order(self.session, self.cash_order, self.other)

    def test_admin_log_checks_role_and_participates_in_the_callers_transaction(self):
        with self.assertRaisesRegex(RuntimeError, "abort workflow"):
            with self.session.begin():
                with self.assertRaises(PermissionError):
                    record_admin_action(
                        self.session, admin_id=self.customer, action_code="sample",
                        target_type="booking", target_id=self.booking, reason="Example",
                    )
                record_admin_action(
                    self.session, admin_id=self.admin, action_code="sample",
                    target_type="booking", target_id=self.booking, reason="Example",
                )
                raise RuntimeError("abort workflow")
        with self.session.begin():
            self.assertEqual(self.session.scalar(select(func.count()).select_from(ActionLog)), 0)

    def test_suspended_user_cannot_read_own_booking(self):
        with self.session.begin():
            self.session.get(User, self.customer).status = UserStatus.SUSPENDED
            with self.assertRaises(PermissionError):
                list_booking_sessions(self.session, self.booking, self.customer)


if __name__ == "__main__":
    unittest.main()
