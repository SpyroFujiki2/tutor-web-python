"""End-to-end domain workflows against an isolated, FK-enabled SQLite fixture.

These exercise HTTP authorization and atomicity, not PostgreSQL row locking.
"""

import secrets
import unittest
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import DefaultClause, Integer, JSON, MetaData, create_engine, event, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import JWTSettings, Settings, get_jwt_settings
from app.core.security import hash_password
from app.main import create_app
from app.models import (
    ActionLog, AuthSession, Base, Booking, BookingSession, BookingSettlement, CashOrder,
    CourseProgress, ExternalTransaction, InternalTransaction, User, UserSubscription, Wallet,
)
from app.models.enums import UserRole, UserStatus, WalletType
from app.modules.common import now
from app.modules.finance.payments import platform_wallet


class DomainApiFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = 'Domain-test-password-123'
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)

        @event.listens_for(self.engine, 'connect')
        def foreign_keys(connection, _record):
            connection.execute('PRAGMA foreign_keys=ON')

        metadata = MetaData()
        for table in Base.metadata.sorted_tables:
            table.to_metadata(metadata)
        for table in metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, JSONB):
                    column.type = JSON()
                if column.server_default is not None and str(column.server_default.arg) == 'now()':
                    column.server_default = DefaultClause(text('CURRENT_TIMESTAMP'))
        metadata.tables['messages'].c.id.type = Integer()
        metadata.create_all(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.app = create_app(Settings(cors_origins=('http://localhost:5173',)))
        self.app.state.session_factory = self.factory
        self.app.state.login_rate_limiter.attempts = 1000
        jwt = JWTSettings(secret_key=secrets.token_urlsafe(48))
        self.app.dependency_overrides[get_jwt_settings] = lambda: jwt
        self.client = TestClient(self.app, raise_server_exceptions=True)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.client.close)
        self.ids = {name: uuid4() for name in ('customer', 'other', 'tutor', 'admin', 'head')}
        with self.factory.begin() as session:
            for name, role in [('customer', UserRole.STUDENT), ('other', UserRole.MEMBER), ('tutor', UserRole.TUTOR), ('admin', UserRole.ADMIN), ('head', UserRole.HEAD_ADMIN)]:
                session.add(User(id=self.ids[name], email=f'{name}@example.com', password_hash=self.password_hash,
                                 role=role, status=UserStatus.ACTIVE, created_at=now()))
            session.flush()
            for name, identity in self.ids.items():
                session.add(Wallet(id=uuid4(), user_id=identity, type=WalletType.NORMAL, available_balance=1000,
                                   holding_balance=0, debt=0, is_active=True, created_at=now()))
            session.add(Wallet(id=uuid4(), user_id=self.ids['tutor'], type=WalletType.COMMERCIAL,
                               available_balance=0, holding_balance=0, debt=0, commission_rate=10, is_active=True))
            platform_wallet(session)
        self.tokens = {}
        for name in self.ids:
            response = self.client.post('/api/auth/login', json={'email': f'{name}@example.com', 'password': self.password})
            self.assertEqual(response.status_code, 200, response.text)
            self.tokens[name] = response.json()

    def request(self, method, path, body=None, *, who='customer', expected=200):
        response = self.client.request(method, '/api' + path, json=body,
                                       headers={'Authorization': 'Bearer ' + self.tokens[who]['access_token']} if who else {})
        self.assertEqual(response.status_code, expected, response.text)
        return response.json() if response.status_code != 204 else None

    def create_course(self, *, live=False, price=100):
        course = self.request('POST', '/admin/courses', {'title': 'Python', 'description': 'Course', 'price': price, 'is_live': live}, who='admin', expected=201)
        lesson = self.request('POST', f"/admin/courses/{course['id']}/lessons", {'order_idx': 1, 'duration_minutes': 10, 'media_url': 'https://example.com/lesson'}, who='admin', expected=201)
        return course, lesson

    def purchase(self, course, request_id=None, who='customer', expected=200):
        return self.request('POST', f"/courses/{course['id']}/purchase", {'request_id': str(request_id or uuid4())}, who=who, expected=expected)

    def create_booking(self, *, price=100):
        package = self.request('POST', '/admin/tutoring-packages', {'name': 'Math', 'price': price}, who='admin', expected=201)
        booking = self.request('POST', '/bookings', {'request_id': str(uuid4()), 'package_id': package['id'], 'subject': 'Math', 'sessions': [{}]}, expected=201)
        return booking

    def paid_booking(self):
        booking = self.create_booking()
        return self.request('POST', f"/bookings/{booking['id']}/pay")

    def completed_booking(self):
        booking = self.paid_booking()
        self.request('POST', f"/admin/bookings/{booking['id']}/assign", {'tutor_id': str(self.ids['tutor'])}, who='admin')
        session_row = self.request('GET', f"/bookings/{booking['id']}/sessions")[0]
        with self.factory.begin() as session:
            row = session.get(BookingSession, UUID(session_row['id']))
            row.starts_at, row.ends_at = now() - timedelta(hours=2), now() - timedelta(hours=1)
        self.request('POST', f"/bookings/{booking['id']}/sessions/{session_row['id']}/action", {'action': 'complete'}, who='tutor')
        self.request('POST', f"/bookings/{booking['id']}/complete")
        return booking

    def balance(self, name='customer', kind=WalletType.NORMAL):
        with self.factory() as session:
            return session.scalar(select(Wallet.available_balance).where(Wallet.user_id == self.ids[name], Wallet.type == kind))

class DomainApiTests(DomainApiFixture):
    def test_register_creates_safe_role_and_wallet_and_rejects_mass_assignment(self):
        payload = {'email': 'NEW@EXAMPLE.COM', 'password': 'new-password-123'}
        self.request('POST', '/auth/register', {**payload, 'role': 'head_admin'}, who=None, expected=422)
        user = self.request('POST', '/auth/register', payload, who=None, expected=201)
        self.assertEqual(user['role'], 'member')
        self.assertEqual(user['email'], 'new@example.com')
        self.assertNotIn('password_hash', user)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(Wallet.available_balance).where(Wallet.user_id == UUID(user['id']))), 0)
        self.request('POST', '/auth/register', payload, who=None, expected=400)

    def test_all_admin_routes_reject_non_admin_and_private_routes_require_auth(self):
        for path in ['/admin/courses', '/admin/cash-orders', '/admin/action-logs', '/admin/users', '/admin/disputes']:
            self.request('GET', path, expected=403)
        for path in ['/me/wallets', '/me/subscriptions', '/bookings', '/posts']:
            self.request('GET', path, who=None, expected=401)
        self.request('GET', '/courses?limit=101', who=None, expected=422)

    def test_course_purchase_retry_is_atomic_and_does_not_double_debit(self):
        course, lesson = self.create_course()
        identity = uuid4()
        first = self.purchase(course, identity)
        second = self.purchase(course, identity)
        self.assertEqual(first, second)
        self.assertEqual(self.balance(), 900)
        self.purchase(course, identity, who='other', expected=400)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(InternalTransaction)), 1)
            self.assertIsNotNone(session.get(CourseProgress, identity))
        self.assertEqual(self.request('GET', f"/subscriptions/{first['id']}/lessons")[0]['id'], lesson['id'])

    def test_insufficient_balance_rolls_back_subscription_progress_and_ledger(self):
        course, _ = self.create_course(price=1001)
        identity = uuid4()
        self.purchase(course, identity, expected=400)
        self.assertEqual(self.balance(), 1000)
        with self.factory() as session:
            self.assertIsNone(session.get(UserSubscription, identity))
            self.assertIsNone(session.get(CourseProgress, identity))
            self.assertEqual(session.scalar(select(func.count()).select_from(InternalTransaction)), 0)

    def test_paid_hidden_course_and_expired_subscription_access(self):
        course, _ = self.create_course()
        sub = self.purchase(course)
        self.request('PUT', f"/admin/courses/{course['id']}", {'title': 'Python', 'price': 100, 'is_live': False, 'status': 'hidden'}, who='admin')
        self.assertEqual(self.request('GET', '/courses', who=None), [])
        self.request('GET', f"/subscriptions/{sub['id']}/lessons")
        self.request('GET', f"/subscriptions/{sub['id']}/lessons", who='other', expected=404)
        with self.factory.begin() as session:
            session.get(UserSubscription, UUID(sub['id'])).expired_at = now() - timedelta(seconds=1)
        self.request('GET', f"/subscriptions/{sub['id']}/lessons", expected=403)
        self.request('GET', f"/subscriptions/{sub['id']}/progress")

    def test_vod_attendance_never_accepts_client_grades_and_completion_is_atomic(self):
        course, lesson = self.create_course()
        sub = self.purchase(course)
        path = f"/subscriptions/{sub['id']}/lessons/{lesson['id']}/watch"
        self.request('POST', path, {'duration_watched': 600, 'final_score': 100}, expected=422)
        progress = self.request('POST', path, {'duration_watched': 600})
        self.assertEqual(progress['progress_percent'], '99.99')
        self.assertIsNone(progress['result'])
        self.request('POST', f"/admin/subscriptions/{sub['id']}/grade", {'midterm_score': 90, 'endterm_score': 90, 'practice_score': 90}, expected=403)
        progress = self.request('POST', f"/admin/subscriptions/{sub['id']}/grade", {'midterm_score': 90, 'endterm_score': 90, 'practice_score': 90}, who='admin')
        self.assertEqual(progress['progress_percent'], '100.00')
        self.assertEqual(progress['result'], 'excellent')
        self.assertIsNotNone(progress['completed_at'])
        self.request('POST', path, {'duration_watched': 1})
        self.assertEqual(self.request('GET', f"/subscriptions/{sub['id']}/attendance")[0]['duration_watched'], 600)

    def test_live_attendance_requires_admin_and_matching_course(self):
        course, lesson = self.create_course(live=True)
        sub = self.purchase(course)
        self.request('POST', f"/subscriptions/{sub['id']}/lessons/{lesson['id']}/watch", {'duration_watched': 600}, expected=400)
        path = f"/admin/subscriptions/{sub['id']}/lessons/{lesson['id']}/attendance"
        self.request('POST', path, {'is_absent': False}, who='admin')
        _, other_lesson = self.create_course(live=True)
        self.request('POST', f"/admin/subscriptions/{sub['id']}/lessons/{other_lesson['id']}/attendance", {'is_absent': False}, who='admin', expected=400)

    def test_lesson_reordering_preserves_unique_constraint_and_paid_content(self):
        course, first = self.create_course()
        second = self.request('POST', f"/admin/courses/{course['id']}/lessons", {'order_idx': 2, 'duration_minutes': 5}, who='admin', expected=201)
        result = self.request('POST', f"/admin/courses/{course['id']}/reorder", {'lesson_ids': [second['id'], first['id']]}, who='admin')
        self.assertEqual([row['order_idx'] for row in result], [1, 2])
        self.purchase(course)
        self.request('DELETE', f"/admin/courses/{course['id']}/lessons/{first['id']}", who='admin', expected=400)

    def test_course_refund_is_idempotent_preserves_history_and_removes_content_access(self):
        course, _ = self.create_course()
        sub = self.purchase(course)
        path = f"/admin/subscriptions/{sub['id']}/refund"
        self.request('POST', path, {'reason': 'Course cancelled'}, expected=403)
        for _ in range(2):
            self.request('POST', path, {'reason': 'Course cancelled'}, who='admin')
        self.assertEqual(self.balance(), 1000)
        self.request('GET', f"/subscriptions/{sub['id']}/lessons", expected=403)
        self.request('GET', f"/subscriptions/{sub['id']}/progress")

    def test_booking_requires_sessions_and_payment_retry_does_not_double_debit(self):
        booking = self.create_booking()
        self.assertEqual(len(self.request('GET', f"/bookings/{booking['id']}/sessions")), 1)
        for _ in range(2):
            self.request('POST', f"/bookings/{booking['id']}/pay")
        self.assertEqual(self.balance(), 900)
        self.request('POST', f"/bookings/{booking['id']}/pay", who='other', expected=404)
        self.request('POST', '/bookings', {'request_id': str(uuid4()), 'package_id': booking['package_id'], 'subject': 'Math', 'sessions': []}, expected=422)

    def test_cancel_paid_booking_refunds_once(self):
        booking = self.paid_booking()
        for _ in range(2):
            self.assertEqual(self.request('POST', f"/bookings/{booking['id']}/cancel")['status'], 'refunded')
        self.assertEqual(self.balance(), 1000)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(InternalTransaction)), 2)

    def test_tutor_schedule_conflicts_and_future_completion_are_rejected(self):
        start = datetime.now(UTC) + timedelta(days=2)
        end = start + timedelta(hours=1)
        values = {'starts_at': start.isoformat(), 'ends_at': end.isoformat()}
        for index in range(2):
            booking = self.paid_booking()
            self.request('POST', f"/admin/bookings/{booking['id']}/assign", {'tutor_id': str(self.ids['tutor'])}, who='admin')
            row = self.request('GET', f"/bookings/{booking['id']}/sessions")[0]
            self.request('PUT', f"/bookings/{booking['id']}/sessions/{row['id']}", values, who='tutor', expected=200 if index == 0 else 400)
            self.request('POST', f"/bookings/{booking['id']}/sessions/{row['id']}/action", {'action': 'complete'}, who='tutor', expected=400)
            self.request('POST', f"/bookings/{booking['id']}/sessions/{row['id']}/action", {'action': 'cancel'}, who='tutor', expected=400)

    def test_messages_are_scoped_and_normal_chat_never_leaks_to_admin(self):
        booking = self.paid_booking()
        path = f"/bookings/{booking['id']}/messages"
        self.request('POST', path, {'content': 'Hello'}, expected=201)
        self.assertEqual(len(self.request('GET', path)), 1)
        self.request('GET', path, who='admin', expected=404)
        self.request('GET', path, who='other', expected=404)
        dispute = self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'No tutor'})
        self.request('POST', f"/admin/disputes/{dispute['id']}/claim", who='admin')
        self.request('POST', path + f"?dispute_id={dispute['id']}", {'content': 'Evidence'}, who='admin', expected=201)
        self.assertEqual(len(self.request('GET', path)), 1)
        self.assertEqual(len(self.request('GET', path + f"?dispute_id={dispute['id']}", who='admin')), 1)

    def test_settlement_holds_then_releases_once(self):
        booking = self.completed_booking()
        settlement = self.request('GET', '/me/settlements', who='tutor')[0]
        self.assertEqual(settlement['tutor_income'], 90)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 0)
        self.request('POST', f"/admin/settlements/{settlement['id']}/release", who='admin', expected=400)
        with self.factory.begin() as session:
            session.get(BookingSettlement, UUID(settlement['id'])).release_date = now() - timedelta(seconds=1)
        for _ in range(2):
            self.request('POST', f"/admin/settlements/{settlement['id']}/release", who='admin')
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 90)
        self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Late'}, expected=400)

    def test_dispute_freezes_release_and_partial_refund_conserves_money(self):
        booking = self.completed_booking()
        dispute = self.request('POST', f"/bookings/{booking['id']}/dispute", {'reason_category': 'Quality'})
        self.request('POST', f"/admin/disputes/{dispute['id']}/claim", who='admin')
        settlement = self.request('GET', '/me/settlements', who='tutor')[0]
        self.request('POST', f"/admin/settlements/{settlement['id']}/release", who='head', expected=400)
        payload = {'verdict': 'refund_partial', 'refund_amount': 40, 'reason': 'Agreed adjustment'}
        self.request('POST', f"/admin/disputes/{dispute['id']}/decision", payload, who='head', expected=403)
        self.request('POST', f"/admin/disputes/{dispute['id']}/decision", payload, who='admin')
        self.assertEqual(self.balance(), 940)
        self.assertEqual(self.balance('tutor', WalletType.COMMERCIAL), 54)
        self.request('POST', f"/admin/disputes/{dispute['id']}/decision", payload, who='admin', expected=400)

    def test_deposit_snapshot_confirm_retry_and_permission(self):
        package = self.request('POST', '/admin/credit-packages', {'name': 'Credits', 'credits': 200, 'price': 50000}, who='admin', expected=201)
        values = {'package_id': package['id'], 'request_id': str(uuid4())}
        order = self.request('POST', '/me/deposits', values, expected=201)
        self.assertEqual(self.request('POST', '/me/deposits', values, expected=201)['id'], order['id'])
        self.request('PUT', f"/admin/credit-packages/{package['id']}", {'name': 'New price', 'credits': 400, 'price': 90000}, who='admin')
        path = f"/admin/cash-orders/{order['id']}/decision"
        self.request('POST', path, {'success': True, 'reason': 'Bank statement'}, who='admin', expected=403)
        for _ in range(2):
            self.request('POST', path, {'success': True, 'reason': 'Bank statement'}, who='head')
        self.assertEqual(self.balance(), 1200)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(ExternalTransaction)), 1)
        self.request('POST', path, {'success': False, 'reason': 'No'}, who='head', expected=400)

    def test_pending_withdrawal_reserves_funds_and_bank_details_are_masked(self):
        bank = self.request('POST', '/me/payment-methods', {'bank_name': 'Example Bank', 'account_number': '123456789', 'account_holder_name': 'Customer'}, expected=201)
        self.assertNotIn('account_number', bank)
        self.assertEqual(bank['account_number_masked'], '****6789')
        order = self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'payment_method_id': bank['id'], 'amount': 950}, expected=201)
        self.assertNotIn('bank_info', order)
        self.request('DELETE', f"/me/payment-methods/{bank['id']}", expected=400)
        course, _ = self.create_course()
        self.purchase(course, expected=400)
        self.request('POST', f"/admin/cash-orders/{order['id']}/decision", {'success': False, 'reason': 'Cancelled transfer'}, who='head')
        self.purchase(course)
        self.assertEqual(self.balance(), 900)

    def test_successful_withdrawal_debits_once_and_does_not_leak_bank_details(self):
        bank = self.request('POST', '/me/payment-methods', {'bank_name': 'Example Bank', 'account_number': '123456789', 'account_holder_name': 'Customer'}, expected=201)
        order = self.request('POST', '/me/withdrawals', {'request_id': str(uuid4()), 'payment_method_id': bank['id'], 'amount': 300}, expected=201)
        path = f"/admin/cash-orders/{order['id']}/bank-details"
        self.request('GET', path, who='admin', expected=403)
        self.assertEqual(self.request('GET', path, who='head')['account_number'], '123456789')
        for _ in range(2):
            self.request('POST', f"/admin/cash-orders/{order['id']}/decision", {'success': True, 'reason': 'Bank transfer 1'}, who='head')
        self.assertEqual(self.balance(), 700)
        history = self.request('GET', '/me/wallets/normal/external-history')
        self.assertEqual(history[0]['balance_after'], 700)
        self.assertNotIn('source_wallet_id', history[0])

    def test_post_visibility_reply_boundaries_and_report_moderation(self):
        post = self.request('POST', '/posts', {'title': 'Private', 'content': 'For students', 'min_role_level': 2}, expected=201)
        self.assertEqual(self.request('GET', '/posts', who='other'), [])
        self.request('GET', f"/posts/{post['id']}", who='other', expected=403)
        comment = self.request('POST', f"/posts/{post['id']}/comments", {'content': 'Hello'}, expected=201)
        second = self.request('POST', '/posts', {'title': 'Second', 'content': 'Body'}, expected=201)
        self.request('POST', f"/posts/{second['id']}/comments", {'content': 'Wrong parent', 'parent_id': comment['id']}, expected=400)
        report = self.request('POST', f"/comments/{comment['id']}/reports", {'reason_category': 'Spam'}, who='tutor', expected=201)
        self.request('POST', f"/admin/reports/{report['id']}/claim", who='admin')
        context = self.request('GET', f"/admin/reports/{report['id']}/context", who='admin')
        self.assertEqual(context['comment']['content'], 'Hello')
        self.request('GET', f"/admin/reports/{report['id']}/context", who='head', expected=403)
        self.request('POST', f"/admin/reports/{report['id']}/decision", {'approve': True, 'reason': 'Spam confirmed'}, who='admin')
        self.assertEqual(self.request('GET', f"/posts/{post['id']}/comments"), [])

    def test_role_promotions_lock_snapshot_and_prohibit_privilege_escalation(self):
        request = self.request('POST', '/me/role-requests', {'request_note': 'Promotion'}, who='tutor', expected=201)
        self.request('POST', '/me/role-requests', {'request_note': 'Duplicate'}, who='tutor', expected=400)
        path = f"/admin/role-requests/{request['id']}/decision"
        self.request('POST', path, {'approve': True, 'reason': 'Approved'}, who='admin', expected=403)
        self.request('POST', path, {'approve': True, 'reason': 'Approved'}, who='head')
        self.assertEqual(self.request('GET', '/auth/me', who='tutor')['role'], 'admin')
        self.request('POST', path, {'approve': True, 'reason': 'Retry'}, who='head', expected=400)

    def test_password_change_and_status_changes_revoke_sessions(self):
        self.request('POST', '/auth/change-password', {'old_password': 'wrong', 'new_password': 'new-password'}, expected=403)
        self.request('POST', '/auth/change-password', {'old_password': self.password, 'new_password': 'new-password'}, expected=204)
        self.request('GET', '/auth/me', expected=401)
        self.request('POST', f"/admin/users/{self.ids['other']}/status", {'status': 'suspended', 'reason': 'Moderation'}, who='admin')
        self.request('GET', '/auth/me', who='other', expected=401)

    def test_snapshot_is_idempotent_and_admin_audit_does_not_contain_secrets(self):
        first = self.request('POST', '/admin/jobs/snapshots', who='admin')
        second = self.request('POST', '/admin/jobs/snapshots', who='admin')
        self.assertEqual(first, second)
        self.create_course()
        logs = self.request('GET', '/admin/action-logs', who='admin')
        self.assertTrue(logs)
        self.assertNotIn('password_hash', str(logs))
        self.assertNotIn(self.password, str(logs))

    def test_put_delete_cors_and_cache_headers(self):
        response = self.client.options('/api/me/payment-methods/' + str(uuid4()), headers={
            'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'DELETE',
            'Access-Control-Request-Headers': 'Authorization, Content-Type',
        })
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/api/me/wallets', headers={'Authorization': 'Bearer ' + self.tokens['customer']['access_token']})
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_session_management_never_exposes_refresh_hash_or_revokes_other_users(self):
        second = self.client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': self.password}).json()
        sessions = self.request('GET', '/auth/sessions')
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sum(row['is_current'] for row in sessions), 1)
        self.assertEqual(set(sessions[0]), {'id', 'created_at', 'expires_at', 'is_current'})
        other = self.request('GET', '/auth/sessions', who='other')[0]
        self.request('POST', f"/auth/sessions/{other['id']}/revoke", expected=404)
        target = next(row for row in sessions if not row['is_current'])
        self.request('POST', f"/auth/sessions/{target['id']}/revoke", expected=204)
        denied = self.client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + second['access_token']})
        self.assertEqual(denied.status_code, 401)
        self.request('GET', '/auth/me')

    def test_email_change_validates_password_normalizes_email_and_revokes_sessions(self):
        self.request('POST', '/auth/change-email', {'email': 'new@example.com', 'password': 'wrong'}, expected=403)
        self.request('POST', '/auth/change-email', {'email': 'other@example.com', 'password': self.password}, expected=400)
        updated = self.request('POST', '/auth/change-email', {'email': 'New@EXAMPLE.COM', 'password': self.password})
        self.assertEqual(updated['email'], 'new@example.com')
        self.request('GET', '/auth/me', expected=401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'customer@example.com', 'password': self.password}).status_code, 401)
        self.assertEqual(self.client.post('/api/auth/login', json={'email': 'new@example.com', 'password': self.password}).status_code, 200)

    def test_session_cleanup_requires_admin_and_keeps_recent_history(self):
        old_id, recent_id = uuid4(), uuid4()
        with self.factory.begin() as session:
            for identity, days in [(old_id, 40), (recent_id, 2)]:
                session.add(AuthSession(id=identity, user_id=self.ids['customer'], refresh_token_hash='0' * 64,
                    created_at=datetime.now(UTC) - timedelta(days=days + 1), expires_at=datetime.now(UTC) - timedelta(days=days)))
        self.request('POST', '/auth/admin/cleanup-sessions', expected=403)
        self.assertEqual(self.request('POST', '/auth/admin/cleanup-sessions', who='admin')['deleted'], 1)
        with self.factory() as session:
            self.assertIsNone(session.get(AuthSession, old_id))
            self.assertIsNotNone(session.get(AuthSession, recent_id))

    def test_comment_cursor_preserves_replies_without_leaking_hidden_parent(self):
        post = self.request('POST', '/posts', {'title': 'Discussion', 'content': 'Welcome'}, expected=201)
        parent = self.request('POST', f"/posts/{post['id']}/comments", {'content': 'Hidden parent content'}, expected=201)
        reply = self.request('POST', f"/posts/{post['id']}/comments", {'content': 'Visible child', 'parent_id': parent['id']}, who='other', expected=201)
        older = self.request('GET', f"/posts/{post['id']}/comments?limit=1")
        after = self.request('GET', f"/posts/{post['id']}/comments?after_id={older[0]['id']}")
        self.assertEqual(after[0]['id'], reply['id'])
        self.request('POST', f"/comments/{parent['id']}/visibility", {'is_hidden': True, 'reason': 'Author hides'}, who='customer')
        visible = self.request('GET', f"/posts/{post['id']}/comments")
        self.assertEqual(len(visible), 1)
        self.assertEqual(visible[0]['parent_id'], parent['id'])
        self.assertNotIn('Hidden parent content', str(visible))

    def test_post_cursor_respects_role_and_literal_search_filters(self):
        for title in ['100% Python', '1000 Python', 'Private']:
            self.request('POST', '/posts', {'title': title, 'content': 'Text', 'min_role_level': 2 if title == 'Private' else 0}, expected=201)
        self.assertEqual(len(self.request('GET', '/posts?q=100%25')), 1)
        first = self.request('GET', '/posts?limit=1', who='other')[0]
        after = self.request('GET', f"/posts?before_id={first['id']}", who='other')
        self.assertEqual(len(after), 1)
        self.assertNotEqual(after[0]['id'], first['id'])

    def test_duplicate_reports_are_idempotent_and_report_rate_limit_is_enforced(self):
        post = self.request('POST', '/posts', {'title': 'Discussion', 'content': 'Text'}, expected=201)
        comments = [self.request('POST', f"/posts/{post['id']}/comments", {'content': f'Comment {index}'}, expected=201) for index in range(6)]
        first = None
        for index, comment in enumerate(comments):
            result = self.request('POST', f"/comments/{comment['id']}/reports", {'reason_category': 'Spam'}, who='tutor', expected=201 if index < 5 else 429)
            if index == 0:
                first = result
        duplicate = self.request('POST', f"/comments/{comments[0]['id']}/reports", {'reason_category': 'Spam'}, who='tutor', expected=201)
        self.assertEqual(first['id'], duplicate['id'])

    def test_stale_or_inactive_role_requests_can_be_rejected_but_not_approved(self):
        request = self.request('POST', '/me/role-requests', {'request_note': 'Apply for tutor'}, who='other', expected=201)
        with self.factory.begin() as session:
            session.get(User, self.ids['other']).role = UserRole.STUDENT
        path = f"/admin/role-requests/{request['id']}/decision"
        self.request('POST', path, {'approve': True, 'reason': 'Review'}, who='head', expected=400)
        result = self.request('POST', path, {'approve': False, 'reason': 'Role changed; please reapply'}, who='head')
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(self.request('GET', '/auth/me', who='other')['role'], 'student')

    def test_message_cursor_is_scoped_to_booking_and_channel(self):
        booking = self.paid_booking()
        path = f"/bookings/{booking['id']}/messages"
        first = self.request('POST', path, {'content': 'First'}, expected=201)
        latest = self.request('POST', path, {'content': 'Latest'}, expected=201)
        self.assertEqual(self.request('GET', path + '?limit=1')[0]['id'], latest['id'])
        self.assertEqual(self.request('GET', path + f"?before_id={latest['id']}")[0]['id'], first['id'])
        other_booking = self.paid_booking()
        self.request('GET', f"/bookings/{other_booking['id']}/messages?before_id={latest['id']}", expected=404)

    def test_admin_audit_uses_allowlisted_snapshots(self):
        from app.modules.users.action_log import record_admin_action
        with self.factory.begin() as session:
            record_admin_action(session, admin_id=self.ids['admin'], action_code='user.status', target_type='users',
                target_id=self.ids['other'], reason='Review', old_value={'password_hash': 'secret', 'role': 'member'},
                new_value={'status': 'suspended', 'access_token': 'secret', 'bank_info': {'account_number': 'private'}})
        row = self.request('GET', f"/admin/action-logs?target_id={self.ids['other']}", who='admin')[0]
        self.assertEqual(row['old_value'], {'role': 'member'})
        self.assertEqual(row['new_value'], {'status': 'suspended'})


if __name__ == '__main__':
    unittest.main()
