"""Opt-in row-lock tests in a disposable PostgreSQL schema, never public tables.

TUTOR_TEST_POSTGRES=1 python -m unittest discover -s tests -p test_postgres_concurrency.py
Only a loopback DATABASE_URL is accepted. Requires CREATE SCHEMA privilege.
"""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_database_settings
from app.models import Base, BookingSession, CashOrder, Course, CreditPackage, InternalTransaction, Lesson, TutoringPackage, User, Wallet
from app.models.enums import CourseStatus, UserRole, UserStatus, WalletType
from app.modules.common import now
from app.modules.finance.payments import create_deposit, decide_cash_order, platform_wallet
from app.modules.learning.learning_service import purchase_course
from app.modules.tutoring.tutoring_service import assign_tutor, cancel_booking, create_booking, pay_booking, schedule_session


@unittest.skipUnless(os.environ.get('TUTOR_TEST_POSTGRES') == '1', 'Set TUTOR_TEST_POSTGRES=1 for isolated PostgreSQL tests')
class PostgreSQLFixture(unittest.TestCase):
    def setUp(self):
        settings = get_database_settings()
        if settings.url.host not in {'localhost', '127.0.0.1', '::1'}:
            self.fail('Concurrency tests require a loopback PostgreSQL host')
        self.schema = 'tutor_test_' + uuid4().hex
        self.control = create_engine(settings.url, hide_parameters=True, connect_args={'connect_timeout': 5})
        self.addCleanup(self.control.dispose)
        with self.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.drop_schema)
        self.engine = create_engine(settings.url, hide_parameters=True, connect_args={
            'connect_timeout': 5,
            'options': f'-c search_path={self.schema} -c timezone=UTC -c lock_timeout=5000 -c statement_timeout=15000',
        })
        self.addCleanup(self.engine.dispose)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.customer, self.tutor, self.admin, self.course, self.lesson, self.package, self.credits = [uuid4() for _ in range(7)]
        with self.factory.begin() as session:
            session.add_all([User(id=identity, role=role, status=UserStatus.ACTIVE) for identity, role in (
                (self.customer, UserRole.STUDENT), (self.tutor, UserRole.TUTOR), (self.admin, UserRole.HEAD_ADMIN))])
            session.add(Course(id=self.course, title='Concurrency', price=100, status=CourseStatus.VISIBLE, is_live=False, created_at=now(), updated_at=now()))
            session.add(TutoringPackage(id=self.package, name='Tutoring', price=100, is_active=True))
            session.add(CreditPackage(id=self.credits, name='Deposit', price=200, credits=200, is_active=True))
            session.flush()
            session.add(Lesson(id=self.lesson, course_id=self.course, order_idx=1, duration_minutes=10))
            session.add(Wallet(id=uuid4(), user_id=self.customer, type=WalletType.NORMAL, available_balance=1000, holding_balance=0, debt=0, is_active=True))
            session.add(Wallet(id=uuid4(), user_id=self.tutor, type=WalletType.COMMERCIAL, available_balance=0, holding_balance=0, debt=0, commission_rate=10, is_active=True))
            platform_wallet(session)

    def drop_schema(self):
        # Identifier comes exclusively from uuid4 above; never from user input.
        self.assertRegex(self.schema, r'^tutor_test_[0-9a-f]{32}$')
        with self.control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(operation):
            try:
                with self.factory.begin() as session:
                    barrier.wait(timeout=10)
                    operation(session)
                return 'ok'
            except ValueError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def balance(self):
        with self.factory() as session:
            return session.scalar(select(Wallet.available_balance).where(Wallet.user_id == self.customer))

    def booking(self):
        with self.factory.begin() as session:
            row = create_booking(session, self.customer, {'request_id': uuid4(), 'package_id': self.package,
                'subject': 'Math', 'requirements': '', 'sessions': [{}]})
            pay_booking(session, self.customer, row.id)
            assign_tutor(session, self.admin, row.id, self.tutor)
            identity = session.scalar(select(BookingSession.id).where(BookingSession.booking_id == row.id))
            return row.id, identity

class PostgreSQLConcurrencyTests(PostgreSQLFixture):
    def test_same_purchase_request_debits_once_under_concurrency(self):
        request_id = uuid4()
        operation = lambda session: purchase_course(session, self.customer, self.course, request_id)
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        self.assertEqual(self.balance(), 900)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(InternalTransaction)), 1)

    def test_two_expensive_purchases_cannot_overdraw_wallet(self):
        with self.factory.begin() as session:
            session.get(Course, self.course).price = 700
        self.assertCountEqual(self.race(
            lambda session: purchase_course(session, self.customer, self.course, uuid4()),
            lambda session: purchase_course(session, self.customer, self.course, uuid4()),
        ), ['ok', 'rejected'])
        self.assertEqual(self.balance(), 300)

    def test_cash_confirmation_is_idempotent_under_concurrency(self):
        with self.factory.begin() as session:
            order = create_deposit(session, self.customer, uuid4(), self.credits)
        operation = lambda session: decide_cash_order(session, self.admin, order.id, True, 'Test bank reference')
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        self.assertEqual(self.balance(), 1200)

    def test_same_tutor_cannot_receive_overlapping_schedules(self):
        first, first_session = self.booking()
        second, second_session = self.booking()
        start = datetime.now(UTC) + timedelta(days=2)
        values = {'starts_at': start, 'ends_at': start + timedelta(hours=1)}
        self.assertCountEqual(self.race(
            lambda session: schedule_session(session, self.tutor, first, values, first_session),
            lambda session: schedule_session(session, self.tutor, second, values, second_session),
        ), ['ok', 'rejected'])

    def test_parallel_cancellations_refund_once(self):
        with self.factory.begin() as session:
            row = create_booking(session, self.customer, {'request_id': uuid4(), 'package_id': self.package,
                'subject': 'Math', 'requirements': '', 'sessions': [{}]})
            pay_booking(session, self.customer, row.id)
        operation = lambda session: cancel_booking(session, self.customer, row.id)
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        self.assertEqual(self.balance(), 1000)

    def test_parallel_vnpay_notifications_credit_once(self):
        from app.core.vnpay import VNPAYSettings
        from app.modules.finance.vnpay import apply_ipn, checkout
        from app.models import ExternalTransaction
        settings = VNPAYSettings(tmn_code='TEST1234', hash_secret='test-only-secret',
                                 return_url='http://localhost:5173/payment/vnpay-return')
        identity = uuid4()
        with self.factory.begin() as session:
            checkout(session, self.customer, identity, self.credits, settings, '127.0.0.1')
        params = {'vnp_TmnCode': settings.tmn_code, 'vnp_TxnRef': identity.hex, 'vnp_Amount': '20000',
                  'vnp_ResponseCode': '00', 'vnp_TransactionStatus': '00', 'vnp_TransactionNo': '12345678'}
        def operation(session):
            self.assertIn(apply_ipn(session, params, settings)['RspCode'], {'00', '02'})
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        self.assertEqual(self.balance(), 1200)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 1)


if __name__ == '__main__':
    unittest.main()
