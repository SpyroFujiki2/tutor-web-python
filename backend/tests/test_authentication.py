"""Review checks for password verification, credential lookup and auth schemas."""

import unittest
from uuid import uuid4
from unittest.mock import patch

from argon2 import PasswordHasher
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models import User
from app.models.enums import UserRole, UserStatus
from app.modules.auth.authenticate import authenticate_user
from app.schemas.auth import LoginRequest, TokenResponse


class PasswordVerificationTests(unittest.TestCase):
    def test_verification_handles_correct_wrong_missing_and_malformed_hashes(self):
        password = "  mật khẩu thử nghiệm 🔐  "
        stored_hash = hash_password(password)
        self.assertTrue(verify_password(password, stored_hash)[0])
        self.assertEqual(verify_password(password.strip(), stored_hash), (False, None))
        for invalid_hash in (None, "", "not-a-hash", 123):
            with self.subTest(hash_type=type(invalid_hash).__name__):
                self.assertEqual(verify_password(password, invalid_hash), (False, None))
        for invalid_password in (None, "", 123):
            with self.subTest(password_type=type(invalid_password).__name__):
                self.assertEqual(verify_password(invalid_password, stored_hash), (False, None))

    def test_successful_verification_can_return_an_upgraded_hash(self):
        password = "test password"
        old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(password)
        valid, upgraded_hash = verify_password(password, old_hash)
        self.assertTrue(valid)
        self.assertIsNotNone(upgraded_hash)
        self.assertNotEqual(upgraded_hash, old_hash)
        self.assertTrue(verify_password(password, upgraded_hash)[0])


class AuthenticateUserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = "test password"
        cls.stored_hash = hash_password(cls.password)

    def setUp(self):
        self.engine = create_engine("sqlite://")
        User.__table__.create(self.engine)
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        self.user_id = uuid4()
        with self.session.begin():
            self.session.add(User(
                id=self.user_id, email="member@example.com", password_hash=self.stored_hash,
                role=UserRole.MEMBER, status=UserStatus.ACTIVE,
            ))

    def test_active_user_matches_normalized_email_without_committing(self):
        with patch.object(self.session, "commit", side_effect=AssertionError("Caller must commit")):
            user_id = authenticate_user(self.session, "  MEMBER@EXAMPLE.COM  ", self.password)
        self.assertEqual(user_id, self.user_id)

    def test_wrong_password_and_missing_user_both_return_none(self):
        self.assertIsNone(authenticate_user(self.session, "member@example.com", "incorrect password"))
        self.assertIsNone(authenticate_user(self.session, "missing@example.com", self.password))
        self.assertEqual(self.session.scalar(select(func.count()).select_from(User)), 1)

    def test_missing_credentials_reuse_the_module_dummy_hash(self):
        with patch("app.modules.auth.authenticate.hash_password", side_effect=AssertionError("Reuse the existing dummy hash")):
            self.assertIsNone(authenticate_user(self.session, "missing@example.com", self.password))
            self.session.get(User, self.user_id).password_hash = None
            self.assertIsNone(authenticate_user(self.session, "member@example.com", self.password))

    def test_inactive_or_unconfigured_user_status_is_rejected(self):
        for status in (UserStatus.SUSPENDED, UserStatus.BANNED, None):
            with self.subTest(status=status):
                self.session.get(User, self.user_id).status = status
                self.assertIsNone(authenticate_user(self.session, "member@example.com", self.password))

    def test_missing_or_malformed_password_hash_is_rejected(self):
        for stored_hash in (None, "", "not-a-hash"):
            with self.subTest(hash_kind="empty" if not stored_hash else "malformed"):
                self.session.get(User, self.user_id).password_hash = stored_hash
                self.assertIsNone(authenticate_user(self.session, "member@example.com", self.password))

    def test_rehash_remains_part_of_callers_transaction(self):
        old_hash = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(self.password)
        self.session.get(User, self.user_id).password_hash = old_hash
        self.session.commit()
        self.assertEqual(authenticate_user(self.session, "member@example.com", self.password), self.user_id)
        upgraded_hash = self.session.get(User, self.user_id).password_hash
        self.assertNotEqual(upgraded_hash, old_hash)
        self.session.flush()
        self.session.rollback()
        self.assertEqual(self.session.get(User, self.user_id).password_hash, old_hash)


class AuthSchemaTests(unittest.TestCase):
    def test_email_validation_rejects_blank_and_malformed_addresses(self):
        for email in ("", "   ", "not-an-email", "member@", "@example.com", "member@@example.com", "member@localhost"):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                LoginRequest(email=email, password="test password")

    def test_email_is_normalized_and_described_as_email_in_json_schema(self):
        payload = LoginRequest(email="  Member@EXAMPLE.COM  ", password="test password")
        self.assertEqual(payload.email, "Member@example.com")
        self.assertEqual(LoginRequest.model_json_schema()["properties"]["email"]["format"], "email")

    def test_token_response_rejects_nonpositive_lifetimes(self):
        for name in ("expires_in", "refresh_expires_in"):
            for value in (0, -1):
                values = {
                    "access_token": "test-access", "refresh_token": "test-refresh",
                    "expires_in": 900, "refresh_expires_in": 604800, name: value,
                }
                with self.subTest(field=name, value=value), self.assertRaises(ValidationError):
                    TokenResponse(**values)

    def test_request_masks_password_and_preserves_its_original_characters(self):
        password = "  mật khẩu thử nghiệm 🔐  "
        payload = LoginRequest(email="member@example.com", password=password)
        self.assertNotIn(password, repr(payload))
        self.assertEqual(payload.password.get_secret_value(), password)

    def test_schema_required_fields_lengths_and_bearer_response_contract(self):
        for payload in (
            {}, {"email": "", "password": "test"},
            {"email": "x" * 321, "password": "test"},
            {"email": "member@example.com", "password": ""},
        ):
            with self.subTest(fields=sorted(payload)), self.assertRaises(ValidationError):
                LoginRequest(**payload)
        response = TokenResponse(
            access_token="test-access", refresh_token="test-refresh", expires_in=900, refresh_expires_in=604800,
        )
        self.assertNotIn("test-access", repr(response))
        self.assertNotIn("test-refresh", repr(response))
        self.assertEqual(set(response.model_dump()), {
            "access_token", "refresh_token", "token_type", "expires_in", "refresh_expires_in",
        })
        self.assertEqual(response.model_dump()["access_token"], "test-access")
        with self.assertRaises(ValidationError):
            TokenResponse(
                access_token="test-access", refresh_token="test-refresh", token_type="basic",
                expires_in=900, refresh_expires_in=604800,
            )


if __name__ == "__main__":
    unittest.main()
