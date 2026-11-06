import secrets
import unittest
from unittest.mock import patch
from uuid import uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import JWTSettings, Settings, get_jwt_settings
from app.core.rate_limit import LoginRateLimiter
from app.core.security import decode_token, hash_password, hash_refresh_token, verify_password
from app.main import create_app
from app.models import AuthSession, Base, User
from app.models.enums import UserRole, UserStatus


class AuthApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "  mật khẩu thử nghiệm 🔐  "
        cls.stored_hash = hash_password(cls.password)

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine, tables=[User.__table__, AuthSession.__table__])
        self.factory = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.app = create_app(Settings(cors_origins=()))
        self.app.state.session_factory = self.factory
        self.settings = JWTSettings(secret_key=secrets.token_urlsafe(48))
        self.app.dependency_overrides[get_jwt_settings] = lambda: self.settings
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.client.close)
        self.user_id = uuid4()
        with self.factory.begin() as session:
            session.add(User(
                id=self.user_id, email="member@example.com", password_hash=self.stored_hash,
                role=UserRole.MEMBER, status=UserStatus.ACTIVE,
            ))

    def login(self, **changes):
        return self.client.post("/api/auth/login", json={
            "email": "  MEMBER@EXAMPLE.COM  ", "password": self.password, **changes,
        })

    def authorization(self, tokens):
        return {"Authorization": f"Bearer {tokens['access_token']}"}

    def test_login_commits_session_and_returns_only_public_token_fields(self):
        response = self.login()
        self.assertEqual(response.status_code, 200, response.text)
        tokens = response.json()
        self.assertEqual(set(tokens), {
            "access_token", "refresh_token", "token_type", "expires_in", "refresh_expires_in",
        })
        self.assertEqual(tokens["token_type"], "bearer")
        self.assertGreater(tokens["expires_in"], 0)
        self.assertGreater(tokens["refresh_expires_in"], tokens["expires_in"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        claims = decode_token(tokens["access_token"], self.settings, expected_type="access")
        with self.factory() as session:
            record = session.get(AuthSession, claims.session_id)
            self.assertEqual(record.user_id, self.user_id)
            self.assertEqual(record.refresh_token_hash, hash_refresh_token(tokens["refresh_token"]))
        me = self.client.get("/api/auth/me", headers=self.authorization(tokens))
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json(), {
            "id": str(self.user_id), "email": "member@example.com", "role": "member", "status": "active",
        })

    def test_invalid_credentials_and_inactive_users_have_the_same_error_and_no_session(self):
        failures = [self.login(password="incorrect"), self.login(email="missing@example.com")]
        for status in (UserStatus.SUSPENDED, UserStatus.BANNED):
            with self.factory.begin() as session:
                session.get(User, self.user_id).status = status
            failures.append(self.login())
        with self.factory.begin() as session:
            user = session.get(User, self.user_id)
            user.status = UserStatus.ACTIVE
            user.password_hash = None
        failures.append(self.login())
        for response in failures:
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"detail": "Invalid email or password"})
            self.assertEqual(response.headers["www-authenticate"], "Bearer")
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(AuthSession)), 0)

    def test_password_rehash_is_committed_with_login(self):
        old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(self.password)
        with self.factory.begin() as session:
            session.get(User, self.user_id).password_hash = old_hash
        self.assertEqual(self.login().status_code, 200)
        with self.factory() as session:
            stored = session.get(User, self.user_id).password_hash
            self.assertNotEqual(stored, old_hash)
            self.assertTrue(verify_password(self.password, stored)[0])

    def test_failed_commit_returns_no_tokens_and_rolls_back_session_and_rehash(self):
        old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(self.password)
        with self.factory.begin() as session:
            session.get(User, self.user_id).password_hash = old_hash

        def fail_commit(_session):
            raise RuntimeError("Database commit failed")

        event.listen(self.factory, "before_commit", fail_commit)
        try:
            response = self.login()
        finally:
            event.remove(self.factory, "before_commit", fail_commit)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("access_token", response.text)
        with self.factory() as session:
            self.assertEqual(session.scalar(select(func.count()).select_from(AuthSession)), 0)
            self.assertEqual(session.get(User, self.user_id).password_hash, old_hash)

    def test_refresh_rotates_and_reuse_commits_revocation_before_denial(self):
        tokens = self.login().json()
        response = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(response.status_code, 200, response.text)
        renewed = response.json()
        self.assertNotEqual(tokens["refresh_token"], renewed["refresh_token"])
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/api/auth/me", headers=self.authorization(renewed)).status_code, 200)
        replay = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json(), {"detail": "Invalid refresh token"})
        for pair in (tokens, renewed):
            self.assertEqual(self.client.get("/api/auth/me", headers=self.authorization(pair)).status_code, 401)
        self.assertEqual(self.client.post(
            "/api/auth/refresh", json={"refresh_token": renewed["refresh_token"]},
        ).status_code, 401)
        with self.factory() as session:
            self.assertIsNotNone(session.scalar(select(AuthSession)).revoked_at)

    def test_logout_revokes_only_current_session(self):
        first, second = self.login().json(), self.login().json()
        response = self.client.post("/api/auth/logout", headers=self.authorization(first))
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get("/api/auth/me", headers=self.authorization(first)).status_code, 401)
        self.assertEqual(self.client.post(
            "/api/auth/refresh", json={"refresh_token": first["refresh_token"]},
        ).status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me", headers=self.authorization(second)).status_code, 200)

    def test_protected_routes_reject_missing_invalid_and_refresh_bearers(self):
        tokens = self.login().json()
        for authorization in (None, "Basic invalid", "Bearer invalid", f"Bearer {tokens['refresh_token']}"):
            headers = {"Authorization": authorization} if authorization else {}
            for method, path in (("GET", "/api/auth/me"), ("POST", "/api/auth/logout")):
                with self.subTest(authorization=authorization, path=path):
                    response = self.client.request(method, path, headers=headers)
                    self.assertEqual(response.status_code, 401)
                    self.assertEqual(response.headers["www-authenticate"], "Bearer")
        response = self.client.post("/api/auth/refresh", json={"refresh_token": tokens["access_token"]})
        self.assertEqual(response.status_code, 401)

    def test_status_change_is_applied_to_access_and_refresh(self):
        tokens = self.login().json()
        with self.factory.begin() as session:
            session.get(User, self.user_id).status = UserStatus.SUSPENDED
        self.assertEqual(self.client.get("/api/auth/me", headers=self.authorization(tokens)).status_code, 401)
        self.assertEqual(self.client.post(
            "/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]},
        ).status_code, 401)
        with self.factory() as session:
            self.assertIsNotNone(session.scalar(select(AuthSession)).revoked_at)

    def test_request_validation_rejects_missing_invalid_and_oversized_credentials(self):
        for payload in (
            {}, {"user_id": str(self.user_id)}, {"email": "invalid", "password": self.password},
            {"email": "member@example.com", "password": ""},
            {"email": "member@example.com", "password": "x" * 1025},
        ):
            self.assertEqual(self.client.post("/api/auth/login", json=payload).status_code, 422)
        for token in ("", "x" * 4097):
            self.assertEqual(self.client.post("/api/auth/refresh", json={"refresh_token": token}).status_code, 422)

    def test_login_rate_limit_runs_before_password_verification_and_ignores_forwarded_header(self):
        self.app.state.login_rate_limiter = LoginRateLimiter(attempts=1)
        self.assertEqual(self.login(password="incorrect").status_code, 401)
        with patch("app.api.routes.auth.authenticate_user", side_effect=AssertionError("Must be limited")):
            response = self.client.post(
                "/api/auth/login", json={"email": "another@example.com", "password": self.password},
                headers={"X-Forwarded-For": "203.0.113.5"},
            )
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response.headers["retry-after"]), 0)


class LoginRateLimiterTests(unittest.TestCase):
    def test_windows_expire_and_new_addresses_cannot_evict_existing_limits(self):
        limiter = LoginRateLimiter(attempts=1, window_seconds=60, max_clients=1)
        with patch("app.core.rate_limit.monotonic", return_value=100):
            self.assertIsNone(limiter.consume("first"))
            self.assertEqual(limiter.consume("first"), 60)
            self.assertEqual(limiter.consume("second"), 60)
        with patch("app.core.rate_limit.monotonic", return_value=159.2):
            self.assertEqual(limiter.consume("first"), 1)
        with patch("app.core.rate_limit.monotonic", return_value=160):
            self.assertIsNone(limiter.consume("second"))


if __name__ == "__main__":
    unittest.main()
