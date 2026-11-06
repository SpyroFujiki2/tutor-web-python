"""Internal finance invariants, without calling or configuring a payment provider."""

from datetime import timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, update

from app.models import BookingSettlement, InternalTransaction, Wallet, WalletSnapshot
from app.models.enums import WalletType
from app.modules.common import MAX_CREDITS, now
from app.modules.finance.internal_transaction import transfer
from app.models.enums import TransactionType
from test_domain_api import DomainApiFixture


class FinanceTests(DomainApiFixture):
    def wallet(self, who='customer', kind='normal'):
        return next(row for row in self.request('GET', '/me/wallets', who=who) if row['type'] == kind)

    def bank(self, who='customer'):
        return self.request('POST', '/me/payment-methods', {'bank_name': '  Example   Bank ',
            'account_number': '123-456 789', 'account_holder_name': ' Account   Holder '}, who=who, expected=201)

    def deposit(self, credits=200, who='customer'):
        package = self.request('POST', '/admin/credit-packages', {'name': 'Manual credits', 'credits': credits, 'price': credits}, who='admin', expected=201)
        order = self.request('POST', '/me/deposits', {'request_id': str(uuid4()), 'package_id': package['id']}, who=who, expected=201)
        return order

    def confirm(self, order):
        return self.request('POST', f"/admin/cash-orders/{order['id']}/decision", {'success': True, 'reason': 'Matched manual bank statement'}, who='head')

    def move(self, amount, *, identity=None, who='tutor', source='normal', destination='commercial', expected=200):
        return self.request('POST', '/me/transfers', {'request_id': str(identity or uuid4()), 'source_type': source,
            'destination_type': destination, 'amount': amount}, who=who, expected=expected)

    def released_booking(self):
        booking = self.completed_booking()
        settlement = next(row for row in self.request('GET', '/me/settlements', who='tutor') if row['booking_id'] == booking['id'])
        with self.factory.begin() as session:
            session.get(BookingSettlement, UUID(settlement['id'])).release_date = now() - timedelta(seconds=1)
        self.request('POST', f"/admin/settlements/{settlement['id']}/release", who='admin')
        return booking, settlement

    def withdraw(self, amount, who='customer', kind='normal', confirm=False):
        bank = self.bank(who)
        order = self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'wallet_type': kind,
            'payment_method_id': bank['id'], 'amount': amount}, who=who, expected=201)
        if confirm:
            self.confirm(order)
        return order, bank

    def fund(self, amount=100):
        return self.request('POST', '/admin/finance/treasury/fund', {'request_id': str(uuid4()), 'amount': amount,
            'reason': 'Internal liquidity funding'}, who='head')

    def late_refund(self, booking, expected=200):
        return self.request('POST', f"/admin/bookings/{booking['id']}/refund-released", {'reason': 'Verified service cancellation'}, who='head', expected=expected)

    def test_bank_normalization_duplicate_detection_and_pending_edit_guard(self):
        bank = self.bank()
        self.assertEqual(bank['bank_name'], 'Example Bank')
        self.assertEqual(bank['account_holder_name'], 'Account Holder')
        self.assertEqual(bank['account_number_masked'], '****6789')
        self.request('POST', '/me/payment-methods', {'bank_name': 'Other', 'account_number': '123456789', 'account_holder_name': 'Holder'}, expected=400)
        order = self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'payment_method_id': bank['id'], 'amount': 500}, expected=201)
        changed = {'bank_name': 'Changed bank', 'account_number': '987654321', 'account_holder_name': 'Holder'}
        self.request('PUT', f"/me/payment-methods/{bank['id']}", changed, expected=400)
        self.request('POST', f"/me/cash-orders/{order['id']}/cancel")
        self.request('PUT', f"/me/payment-methods/{bank['id']}", changed)

    def test_cancel_pending_withdrawal_releases_reservation_once_and_checks_owner(self):
        order, _ = self.withdraw(950)
        wallet = self.wallet()
        self.assertEqual(wallet['available_balance'], 1000)
        self.assertEqual(wallet['reserved_withdrawals'], 950)
        self.assertEqual(wallet['spendable_balance'], 50)
        self.request('POST', f"/me/cash-orders/{order['id']}/cancel", who='other', expected=404)
        for _ in range(2):
            self.assertTrue(self.request('POST', f"/me/cash-orders/{order['id']}/cancel")['cancelled_by_user'])
        self.assertEqual(self.wallet()['spendable_balance'], 1000)
        self.request('POST', f"/admin/cash-orders/{order['id']}/decision", {'success': True, 'reason': 'Late confirmation'}, who='head', expected=400)

    def test_own_transfer_is_idempotent_and_rejects_changed_request(self):
        identity = uuid4()
        first = self.move(120, identity=identity)
        self.assertEqual(self.move(120, identity=identity), first)
        self.move(121, identity=identity, expected=400)
        self.assertEqual(self.balance('tutor'), 880)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 120)
        self.move(1, source='normal', destination='normal', expected=400)

    def test_transfers_respect_pending_withdrawals_and_never_expose_counterparty_balances(self):
        order, _ = self.withdraw(990, who='tutor')
        self.move(11, expected=400)
        entry = self.move(10)
        self.assertNotIn('source_balance_before', entry)
        self.assertNotIn('destination_balance_after', entry)
        self.request('POST', f"/me/cash-orders/{order['id']}/cancel", who='tutor')
        self.move(100)

    def test_transfer_retry_returns_original_receipt_even_after_wallet_freeze(self):
        identity = uuid4()
        first = self.move(40, identity=identity)
        wallet = self.wallet('tutor', 'commercial')
        self.request('POST', f"/admin/wallets/{wallet['id']}/status", {'is_active': False, 'reason': 'Review'}, who='head')
        self.assertEqual(self.move(40, identity=identity), first)
        self.move(1, expected=400)

    def test_internal_correction_is_append_only_and_cannot_be_applied_twice(self):
        original = self.move(100)
        request_id = str(uuid4())
        path = f"/admin/internal-transactions/{original['id']}/reverse"
        payload = {'request_id': request_id, 'reason': 'Verified mistaken own transfer'}
        self.request('POST', path, payload, who='admin', expected=403)
        first = self.request('POST', path, payload, who='head')
        self.assertEqual(first, self.request('POST', path, payload, who='head'))
        self.request('POST', path, {**payload, 'request_id': str(uuid4())}, who='head', expected=400)
        self.assertEqual(self.balance('tutor'), 1000)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 0)
        with self.factory() as session:
            self.assertEqual(session.get(InternalTransaction, UUID(original['id'])).amount, 100)
            self.assertEqual(session.scalar(select(func.count()).select_from(InternalTransaction)), 2)

    def test_service_payment_cannot_be_reversed_without_refunding_entitlement(self):
        course, _ = self.create_course()
        self.purchase(course)
        with self.factory() as session:
            identity = session.scalar(select(InternalTransaction.id))
        self.request('POST', f'/admin/internal-transactions/{identity}/reverse', {'request_id': str(uuid4()), 'reason': 'Wrong workflow'}, who='head', expected=400)
        self.assertEqual(self.balance(), 900)

    def test_manual_deposit_correction_restores_balance_with_a_separate_entry(self):
        order = self.deposit()
        self.confirm(order)
        original = self.request('GET', '/me/wallets/normal/external-history')[0]
        path = f"/admin/external-transactions/{original['id']}/reverse"
        payload = {'request_id': str(uuid4()), 'reason': 'Manual bank correction verified'}
        first = self.request('POST', path, payload, who='head')
        self.assertEqual(self.request('POST', path, payload, who='head'), first)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.request('GET', f"/me/cash-orders/{order['id']}")['status'], 'success')
        self.assertEqual(len(self.request('GET', '/me/wallets/normal/external-history')), 2)
        self.request('POST', f"/admin/external-transactions/{first['id']}/reverse", {'request_id': str(uuid4()), 'reason': 'Reverse correction'}, who='head', expected=400)

    def test_manual_withdrawal_correction_credits_back_without_reopening_original_order(self):
        order, _ = self.withdraw(300, confirm=True)
        original = self.request('GET', '/me/wallets/normal/external-history')[0]
        self.request('POST', f"/admin/external-transactions/{original['id']}/reverse", {'request_id': str(uuid4()), 'reason': 'Returned funds verified'}, who='head')
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.request('GET', f"/me/cash-orders/{order['id']}")['status'], 'success')

    def test_freezing_wallet_blocks_spend_but_keeps_history_and_allows_entitlement_refund(self):
        course, _ = self.create_course()
        subscription = self.purchase(course)
        wallet = self.wallet()
        payload = {'is_active': False, 'reason': 'Account review'}
        self.request('POST', f"/admin/wallets/{wallet['id']}/status", payload, who='admin', expected=403)
        self.request('POST', f"/admin/wallets/{wallet['id']}/status", payload, who='head')
        self.assertEqual(self.wallet()['spendable_balance'], 0)
        self.purchase(course, expected=404)
        self.request('GET', '/me/wallets/normal/history')
        self.request('GET', '/me/wallets/normal/external-history')
        self.request('POST', f"/admin/subscriptions/{subscription['id']}/refund", {'reason': 'Approved cancellation'}, who='admin')
        self.assertEqual(self.balance(), 1000)
        self.assertFalse(self.wallet()['is_active'])

    def test_commercial_contract_changes_do_not_rewrite_existing_settlement(self):
        booking = self.completed_booking()
        commercial = self.wallet('tutor', 'commercial')
        self.request('POST', f"/admin/wallets/{commercial['id']}/contract", {'commission_rate': 25, 'contract_id': 'CONTRACT-2', 'reason': 'New terms'}, who='head')
        settlement = self.request('GET', '/me/settlements', who='tutor')[0]
        self.assertEqual(settlement['commission_rate'], 10)
        self.assertEqual(settlement['tutor_income'], 90)
        self.assertEqual(settlement['booking_id'], booking['id'])
        normal = self.wallet('tutor')
        self.request('POST', f"/admin/wallets/{normal['id']}/contract", {'commission_rate': 25, 'reason': 'Invalid type'}, who='head', expected=400)

    def test_escrow_is_reserved_from_platform_spending(self):
        self.completed_booking()
        treasury = self.request('GET', '/admin/finance/treasury', who='admin')
        self.assertEqual(treasury['available_balance'], 100)
        self.assertEqual(treasury['spendable_balance'], 10)
        with self.factory.begin() as session:
            with self.assertRaises(ValueError):
                transfer(session, UUID(treasury['id']), UUID(self.wallet('other')['id']), 11, TransactionType.PAYMENT)

    def test_released_refund_recovers_tutor_balance_and_is_idempotent(self):
        booking, settlement = self.released_booking()
        first = self.late_refund(booking)
        self.assertEqual(first, self.late_refund(booking))
        self.assertEqual(first['id'], settlement['id'])
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 0)
        self.assertEqual(self.wallet('tutor', 'commercial')['debt'], 0)

    def test_late_refund_shortfall_requires_platform_liquidity_before_changing_anything(self):
        booking, _ = self.released_booking()
        self.withdraw(70, who='tutor', kind='commercial', confirm=True)
        self.late_refund(booking, expected=400)
        self.assertEqual(self.balance(), 900)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 20)
        self.assertEqual(self.wallet('tutor', 'commercial')['debt'], 0)
        self.assertEqual(self.request('GET', f"/bookings/{booking['id']}")['status'], 'completed')

    def test_late_refund_cancels_pending_withdrawals_creates_debt_and_blocks_payout(self):
        booking, _ = self.released_booking()
        _, bank = self.withdraw(70, who='tutor', kind='commercial', confirm=True)
        pending = self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'wallet_type': 'commercial', 'payment_method_id': bank['id'], 'amount': 10}, who='tutor', expected=201)
        self.fund()
        self.late_refund(booking)
        self.assertEqual(self.wallet('tutor', 'commercial')['debt'], 70)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.request('GET', f"/me/cash-orders/{pending['id']}", who='tutor')['status'], 'failed')
        self.move(1, destination='commercial', expected=400)
        self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'wallet_type': 'commercial', 'payment_method_id': bank['id'], 'amount': 1}, who='tutor', expected=400)
        self.late_refund(booking)
        self.assertEqual(self.wallet('tutor', 'commercial')['debt'], 70)

    def test_future_tutor_income_automatically_repays_debt_with_separate_ledger_entries(self):
        booking, _ = self.released_booking()
        self.withdraw(70, who='tutor', kind='commercial', confirm=True)
        self.fund()
        self.late_refund(booking)
        self.released_booking()
        wallet = self.wallet('tutor', 'commercial')
        self.assertEqual(wallet['available_balance'], 20)
        self.assertEqual(wallet['debt'], 0)
        report = self.request('GET', f"/admin/wallets/{wallet['id']}/reconciliation", who='admin')
        self.assertEqual(report['status'], 'ok', report)

    def test_explicit_debt_repayment_is_idempotent_and_cannot_exceed_debt(self):
        booking, _ = self.released_booking()
        self.withdraw(70, who='tutor', kind='commercial', confirm=True)
        self.fund()
        self.late_refund(booking)
        payload = {'request_id': str(uuid4()), 'amount': 30}
        first = self.request('POST', '/me/debt-repayments', payload, who='tutor')
        self.assertEqual(first, self.request('POST', '/me/debt-repayments', payload, who='tutor'))
        self.assertEqual(self.wallet('tutor', 'commercial')['debt'], 40)
        self.assertEqual(self.balance('tutor'), 970)
        self.request('POST', '/me/debt-repayments', {'request_id': str(uuid4()), 'amount': 41}, who='tutor', expected=400)

    def test_reconciliation_uses_opening_record_and_detects_balance_tampering_without_repair(self):
        payload = {'email': 'finance-new@example.com', 'password': 'test-password-123'}
        self.request('POST', '/auth/register', payload, who=None, expected=201)
        pair = self.client.post('/api/auth/login', json=payload).json()
        response = self.client.get('/api/me/wallets', headers={'Authorization': 'Bearer ' + pair['access_token']})
        wallet_id = response.json()[0]['id']
        report = self.request('GET', f'/admin/wallets/{wallet_id}/reconciliation', who='admin')
        self.assertEqual(report['baseline_source'], 'recorded')
        self.assertEqual(report['status'], 'ok')
        with self.factory.begin() as session:
            session.get(Wallet, UUID(wallet_id)).available_balance = 17
        report = self.request('GET', f'/admin/wallets/{wallet_id}/reconciliation', who='admin')
        self.assertIn('available_balance_mismatch', [issue['code'] for issue in report['issues']])
        self.assertEqual(report['available_balance'], 17)

    def test_legacy_reconciliation_reports_derived_baseline_and_ledger_corruption(self):
        entry = self.move(80)
        wallet = self.wallet('tutor')
        path = f"/admin/wallets/{wallet['id']}/reconciliation"
        report = self.request('GET', path, who='admin')
        self.assertEqual(report['status'], 'ok')
        self.assertIn('opening_balance_unverified', report['warnings'])
        # Simulate a database operator bypassing the application ORM guard.
        with self.factory.begin() as session:
            session.execute(update(InternalTransaction).where(InternalTransaction.id == UUID(entry['id'])).values(amount=81))
        report = self.request('GET', path, who='admin')
        self.assertIn('checksum_mismatch', [issue['code'] for issue in report['issues']])
        self.assertIn('ledger_balance_equation', [issue['code'] for issue in report['issues']])

    def test_orm_cannot_change_or_delete_monetary_history_or_snapshots(self):
        entry = self.move(50)
        with self.assertRaises(ValueError):
            with self.factory.begin() as session:
                session.get(InternalTransaction, UUID(entry['id'])).amount = 51
        with self.assertRaises(ValueError):
            with self.factory.begin() as session:
                session.delete(session.get(InternalTransaction, UUID(entry['id'])))
        snapshots = self.request('POST', '/admin/jobs/snapshots?limit=2', who='admin')
        with self.assertRaises(ValueError):
            with self.factory.begin() as session:
                session.get(WalletSnapshot, UUID(snapshots[0]['id'])).available_snap = 999

    def test_committed_legacy_ledger_cannot_gain_mutable_metadata_permission(self):
        source, destination = self.wallet('tutor'), self.wallet('tutor', 'commercial')
        identity = uuid4()
        with self.factory.begin() as session:
            session.add(InternalTransaction(id=identity, source_wallet_id=UUID(source['id']), destination_wallet_id=UUID(destination['id']),
                amount=0, type=TransactionType.PAYMENT, source_balance_before=1000, source_balance_after=1000,
                destination_balance_before=0, destination_balance_after=0, created_at=now()))
        with self.assertRaises(ValueError):
            with self.factory.begin() as session:
                session.get(InternalTransaction, identity).checksum = '0' * 64

    def test_late_full_refund_does_not_claim_an_earlier_partial_refund_as_its_own(self):
        booking = self.completed_booking()
        dispute = self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Partial adjustment'})
        self.request('POST', f"/admin/disputes/{dispute['id']}/claim", who='admin')
        self.request('POST', f"/admin/disputes/{dispute['id']}/decision", {'verdict': 'refund_partial', 'refund_amount': 40, 'reason': 'Agreed partial refund'}, who='admin')
        self.late_refund(booking, expected=400)
        self.assertEqual(self.balance(), 940)

    def test_snapshot_batch_is_bounded_and_same_day_history_is_not_overwritten(self):
        first = self.request('POST', '/admin/jobs/snapshots?limit=2&offset=0', who='admin')
        self.assertEqual(len(first), 2)
        self.assertEqual(self.request('POST', '/admin/jobs/snapshots?limit=2&offset=0', who='admin'), first)
        self.request('POST', '/admin/jobs/snapshots?limit=101', who='admin', expected=422)

    def test_admin_ledger_combines_directions_and_pages_without_counterparty_balances(self):
        self.move(30)
        wallet = self.wallet('tutor')
        rows = self.request('GET', f"/admin/wallets/{wallet['id']}/ledger?limit=1", who='admin')
        self.assertEqual(rows[0]['category'], 'internal')
        self.assertEqual(rows[0]['direction'], 'out')
        self.assertEqual(rows[0]['balance_after'], 970)
        self.assertNotIn('destination_balance_before', rows[0])
        self.request('GET', f"/admin/wallets/{wallet['id']}/ledger", expected=403)

    def test_due_release_job_skips_disputing_booking_and_retries_safely(self):
        first = self.completed_booking()
        second = self.completed_booking()
        self.request('POST', f"/bookings/{second['id']}/dispute", {'reason_category': 'Review'})
        with self.factory.begin() as session:
            for row in session.scalars(select(BookingSettlement)):
                row.release_date = now() - timedelta(seconds=1)
        result = self.request('POST', '/admin/jobs/release-settlements', who='admin')
        self.assertEqual(len(result['released']), 1)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 90)
        self.assertEqual(self.request('POST', '/admin/jobs/release-settlements', who='admin')['released'], [])

    def test_int32_overflow_rolls_back_manual_deposit(self):
        order = self.deposit(1)
        wallet = self.wallet()
        with self.factory.begin() as session:
            session.get(Wallet, UUID(wallet['id'])).available_balance = MAX_CREDITS
        self.request('POST', f"/admin/cash-orders/{order['id']}/decision", {'success': True, 'reason': 'Overflow test'}, who='head', expected=400)
        self.assertEqual(self.balance(), MAX_CREDITS)
        self.assertEqual(self.request('GET', f"/me/cash-orders/{order['id']}")['status'], 'pending')

    def test_commit_failure_rolls_back_transfer_balances_and_ledger(self):
        def fail(_session):
            raise RuntimeError('Commit test failure')
        event.listen(self.factory, 'before_commit', fail)
        client = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(client.close)
        try:
            response = client.post('/api/me/transfers', json={'request_id': str(uuid4()), 'source_type': 'normal', 'destination_type': 'commercial', 'amount': 100}, headers={'Authorization': 'Bearer ' + self.tokens['tutor']['access_token']})
        finally:
            event.remove(self.factory, 'before_commit', fail)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.balance('tutor'), 1000)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 0)
