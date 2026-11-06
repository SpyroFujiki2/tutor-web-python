"""Opt-in PostgreSQL finance races; all data lives in a disposable schema."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.models import ActionLog, BookingSession, BookingSettlement, CashOrder, ExternalTransaction, PaymentMethod, User, Wallet, WalletSnapshot
from app.models.enums import BookingSessionStatus, CashOrderStatus, WalletType
from app.modules.common import now
from app.modules.finance.wallet import PLATFORM_USER_ID, PLATFORM_WALLET_ID, platform_wallet
from app.modules.finance.cash_order import cancel_cash_order, create_deposit, create_withdrawal, decide_cash_order
from app.modules.finance.internal_transaction import fund_platform, move_own_credits
from app.modules.finance.external_transaction import reverse_external_transaction
from app.modules.finance.booking_settlement import refund_released_booking, release_settlement
from app.modules.finance.wallet_snapshot import daily_snapshots
from app.modules.tutoring.booking import complete_booking
from test_postgres_concurrency import PostgreSQLFixture


class FinanceConcurrencyTests(PostgreSQLFixture):
    def setUp(self):
        super().setUp()
        self.customer_bank, self.tutor_bank = uuid4(), uuid4()
        with self.factory.begin() as session:
            for user_id in (self.tutor, self.admin):
                session.add(Wallet(id=uuid4(), user_id=user_id, type=WalletType.NORMAL,
                    available_balance=1000, holding_balance=0, debt=0, is_active=True))
            for identity, user_id in [(self.customer_bank, self.customer), (self.tutor_bank, self.tutor)]:
                session.add(PaymentMethod(id=identity, user_id=user_id, bank_name='Fixture Bank', account_number='123456789', account_holder_name='Fixture Holder'))

    def completed(self):
        booking_id, session_id = self.booking()
        with self.factory.begin() as session:
            row = session.get(BookingSession, session_id)
            row.starts_at, row.ends_at = now() - timedelta(hours=2), now() - timedelta(hours=1)
            row.status = BookingSessionStatus.COMPLETED
            session.flush()
            complete_booking(session, self.customer, booking_id)
            settlement = session.scalar(select(BookingSettlement).where(BookingSettlement.booking_id == booking_id))
            settlement.release_date = now() - timedelta(seconds=1)
            return booking_id, settlement.id

    def test_parallel_withdrawals_cannot_reserve_more_than_available(self):
        self.assertCountEqual(self.race(
            lambda session: create_withdrawal(session, self.customer, uuid4(), WalletType.NORMAL, self.customer_bank, 600),
            lambda session: create_withdrawal(session, self.customer, uuid4(), WalletType.NORMAL, self.customer_bank, 600),
        ), ['ok', 'rejected'])
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.sum(CashOrder.credit_amount))), 600)
        self.assertEqual(self.balance(), 1000)

    def test_transfer_racing_with_withdrawal_preserves_reservations(self):
        self.assertCountEqual(self.race(
            lambda session: create_withdrawal(session, self.tutor, uuid4(), WalletType.NORMAL, self.tutor_bank, 600),
            lambda session: move_own_credits(session, self.tutor, uuid4(), WalletType.NORMAL, WalletType.COMMERCIAL, 600),
        ), ['ok', 'rejected'])
        with self.factory() as session:
            available = session.scalar(select(Wallet.available_balance).where(Wallet.user_id == self.tutor, Wallet.type == WalletType.NORMAL))
            pending = session.scalar(select(func.coalesce(func.sum(CashOrder.credit_amount), 0)))
            self.assertGreaterEqual(available, pending)

    def test_confirmation_racing_with_cancellation_never_debits_twice(self):
        with self.factory.begin() as session:
            order = create_withdrawal(session, self.customer, uuid4(), WalletType.NORMAL, self.customer_bank, 300)
        self.assertCountEqual(self.race(
            lambda session: decide_cash_order(session, self.admin, order.id, True, 'Bank transfer verified'),
            lambda session: cancel_cash_order(session, self.customer, order.id),
        ), ['ok', 'rejected'])
        with self.factory() as session:
            status = session.get(CashOrder, order.id).status
            count = session.scalar(select(func.count()).select_from(ExternalTransaction))
            self.assertEqual(count, 1 if status == CashOrderStatus.SUCCESS else 0)
            self.assertEqual(self.balance(), 700 if status == CashOrderStatus.SUCCESS else 1000)

    def test_concurrent_external_corrections_append_one_compensation(self):
        with self.factory.begin() as session:
            order = create_deposit(session, self.customer, uuid4(), self.credits)
            decide_cash_order(session, self.admin, order.id, True, 'Verified deposit')
            original = session.scalar(select(ExternalTransaction.id))
        request_id = uuid4()
        operation = lambda session: reverse_external_transaction(session, self.admin, original, request_id, 'Verified correction')
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        self.assertEqual(self.balance(), 1000)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 2)

    def test_concurrent_releases_pay_tutor_once(self):
        _, identity = self.completed()
        operation = lambda session: release_settlement(session, self.admin, identity)
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        with self.factory() as session:
            wallet = session.scalar(select(Wallet).where(Wallet.user_id == self.tutor, Wallet.type == WalletType.COMMERCIAL))
            self.assertEqual(wallet.available_balance, 90)
            self.assertEqual(wallet.holding_balance, 0)

    def test_late_refund_racing_with_withdrawal_confirmation_preserves_debt(self):
        booking_id, identity = self.completed()
        with self.factory.begin() as session:
            release_settlement(session, self.admin, identity)
            fund_platform(session, self.admin, uuid4(), 100, 'Liquidity reserve')
            order = create_withdrawal(session, self.tutor, uuid4(), WalletType.COMMERCIAL, self.tutor_bank, 70)
        results = self.race(
            lambda session: refund_released_booking(session, self.admin, booking_id, 'Approved cancellation'),
            lambda session: decide_cash_order(session, self.admin, order.id, True, 'Verified payout'),
        )
        self.assertEqual(results[0], 'ok')
        with self.factory() as session:
            status = session.get(CashOrder, order.id).status
            wallet = session.scalar(select(Wallet).where(Wallet.user_id == self.tutor, Wallet.type == WalletType.COMMERCIAL))
            self.assertEqual(wallet.available_balance, 0)
            self.assertEqual(wallet.debt, 70 if status == CashOrderStatus.SUCCESS else 0)
        self.assertEqual(self.balance(), 1000)

    def test_first_platform_initialization_is_safe_across_workers(self):
        with self.factory.begin() as session:
            session.execute(delete(ActionLog).where(ActionLog.target_user_id == PLATFORM_USER_ID))
            session.delete(session.get(Wallet, PLATFORM_WALLET_ID))
            session.flush()
            session.delete(session.get(User, PLATFORM_USER_ID))
        self.assertEqual(self.race(platform_wallet, platform_wallet), ['ok', 'ok'])
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(Wallet).where(Wallet.id == PLATFORM_WALLET_ID)), 1)
            self.assertEqual(session.scalar(select(func.count()).select_from(ActionLog).where(ActionLog.action_code == 'wallet.open', ActionLog.target_id == PLATFORM_WALLET_ID)), 1)

    def test_concurrent_snapshot_jobs_keep_one_record_per_wallet_day(self):
        operation = lambda session: daily_snapshots(session, self.admin)
        self.assertEqual(self.race(operation, operation), ['ok', 'ok'])
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(WalletSnapshot)), session.scalar(select(func.count()).select_from(Wallet)))
