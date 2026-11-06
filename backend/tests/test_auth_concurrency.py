"""Opt-in PostgreSQL checks for token rotation and session revocation races."""

import os
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import jwt
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.config import JWTSettings, get_database_settings
from app.models import AuthSession, User
from app.models.enums import UserRole, UserStatus
from app.modules.auth.current_user import get_authenticated_user
from app.modules.auth.login import issue_login_tokens
from app.modules.auth.refresh import renew_tokens
from app.modules.common import actor
from app.modules.users.accounts import revoke_all


@unittest.skipUnless(os.environ.get('TUTOR_TEST_POSTGRES') == '1', 'Set TUTOR_TEST_POSTGRES=1 for isolated PostgreSQL tests')
class PostgreSQLAuthConcurrencyTests(unittest.TestCase):
    def setUp(self):
        settings = get_database_settings()
        self.assertIn(settings.url.host, {'localhost', '127.0.0.1', '::1'})
        self.schema = 'tutor_auth_test_' + uuid4().hex
        self.control = create_engine(settings.url, hide_parameters=True, connect_args={'connect_timeout': 5})
        self.addCleanup(self.control.dispose)
        with self.control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{self.schema}"'))
        self.addCleanup(self.drop_schema)
        self.engine = create_engine(settings.url, hide_parameters=True, connect_args={
            'connect_timeout': 5, 'options': f'-c search_path={self.schema} -c timezone=UTC -c lock_timeout=5000 -c statement_timeout=15000',
        })
        self.addCleanup(self.engine.dispose)
        User.__table__.create(self.engine)
        AuthSession.__table__.create(self.engine)
        self.factory = sessionmaker(self.engine, expire_on_commit=False)
        self.user_id = uuid4()
        self.jwt = JWTSettings(secret_key=secrets.token_urlsafe(48))
        with self.factory.begin() as session:
            session.add(User(id=self.user_id, role=UserRole.MEMBER, status=UserStatus.ACTIVE))
            session.flush()
            self.tokens = issue_login_tokens(session, self.user_id, self.jwt)

    def drop_schema(self):
        self.assertRegex(self.schema, r'^tutor_auth_test_[0-9a-f]{32}$')
        with self.control.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{self.schema}" CASCADE'))

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(operation):
            with self.factory.begin() as session:
                barrier.wait(timeout=10)
                return operation(session)
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_concurrent_reuse_rotates_once_then_revokes_entire_family(self):
        operation = lambda session: renew_tokens(session, self.tokens.refresh_token, self.jwt)
        results = self.race(operation, operation)
        self.assertEqual(sum(result.tokens is not None for result in results), 1)
        self.assertIn('reused', [result.error for result in results])
        with self.factory() as session:
            self.assertIsNotNone(session.scalar(select(AuthSession.revoked_at)))
            for pair in [self.tokens] + [result.tokens for result in results if result.tokens]:
                with self.assertRaises(jwt.InvalidTokenError):
                    get_authenticated_user(session, pair.access_token, self.jwt)

    def test_logout_all_racing_with_refresh_leaves_no_active_session(self):
        self.race(lambda session: renew_tokens(session, self.tokens.refresh_token, self.jwt),
                  lambda session: revoke_all(session, self.user_id))
        with self.factory() as session:
            self.assertIsNotNone(session.scalar(select(AuthSession.revoked_at)))
            with self.assertRaises(jwt.InvalidTokenError):
                get_authenticated_user(session, self.tokens.access_token, self.jwt)

    def test_suspending_user_racing_with_refresh_cannot_leave_usable_tokens(self):
        def suspend(session):
            actor(session, self.user_id, lock=True).status = UserStatus.SUSPENDED
            revoke_all(session, self.user_id)
        results = self.race(lambda session: renew_tokens(session, self.tokens.refresh_token, self.jwt), suspend)
        with self.factory() as session:
            self.assertIsNotNone(session.scalar(select(AuthSession.revoked_at)))
            pair = results[0].tokens
            for access in [self.tokens.access_token] + ([pair.access_token] if pair else []):
                with self.assertRaises((jwt.InvalidTokenError, PermissionError)):
                    get_authenticated_user(session, access, self.jwt)


if __name__ == '__main__':
    unittest.main()
