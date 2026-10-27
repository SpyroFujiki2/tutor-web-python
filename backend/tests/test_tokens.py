import secrets
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_access_claims
from app.core.config import JWTSettings, get_jwt_settings
from app.core.security import TokenClaims, create_token_pair, decode_token, hash_refresh_token
from app.models import AuthSession, Base, User
from app.models.enums import UserRole, UserStatus
from app.modules.auth.current_user import get_authenticated_user
from app.modules.auth.login import issue_login_tokens
from app.modules.auth.logout import revoke_token_session
from app.modules.auth.refresh import renew_tokens


class JWTClaimsTests(unittest.TestCase):
    def setUp(self):
        self.settings = JWTSettings(secret_key=secrets.token_urlsafe(48))
        self.user_id, self.session_id = uuid4(), uuid4()
        self.pair = create_token_pair(self.user_id, self.session_id, self.settings)

    def test_pair_has_distinct_types_ids_and_lifetimes(self):
        access = decode_token(self.pair.access_token, self.settings, expected_type="access")
        refresh = decode_token(self.pair.refresh_token, self.settings, expected_type="refresh")
        self.assertEqual(access.user_id, self.user_id)
        self.assertEqual(refresh.session_id, self.session_id)
        self.assertNotEqual(access.token_id, refresh.token_id)
        self.assertEqual(self.pair.expires_in, 900)
        self.assertEqual(self.pair.refresh_expires_in, 604800)
        self.assertEqual(self.pair.token_type, "bearer")
        self.assertNotIn(self.pair.access_token, repr(self.pair))

    def test_wrong_signature_algorithm_and_token_type_are_rejected(self):
        other_settings = replace(self.settings, secret_key=secrets.token_urlsafe(48))
        with self.assertRaises(jwt.InvalidTokenError):
            decode_token(self.pair.access_token, other_settings, expected_type="access")
        with self.assertRaises(jwt.InvalidTokenError):
            decode_token(self.pair.refresh_token, self.settings, expected_type="access")
        with self.assertRaises(jwt.InvalidTokenError):
            decode_token(self.pair.access_token, self.settings, expected_type="refresh")
        payload = jwt.decode(self.pair.access_token, options={"verify_signature": False})
        token = jwt.encode(payload, self.settings.secret_key, algorithm="HS512", headers={"typ": "at+jwt"})
        with self.assertRaises(jwt.InvalidTokenError):
            decode_token(token, self.settings, expected_type="access")

    def test_required_claims_times_scope_and_identifier_validation(self):
        payload = jwt.decode(self.pair.access_token, options={"verify_signature": False})
        future = int((datetime.now(UTC) + timedelta(days=1)).timestamp())
        for key, value in (
            ("exp", 0), ("nbf", future), ("iat", future), ("iss", "other-issuer"),
            ("aud", "other-audience"), ("aud", [self.settings.audience]),
            ("sub", "invalid-uuid"), ("sid", []), ("jti", "invalid-uuid"),
            ("iat", True), ("iat", float(payload["iat"])),
        ):
            with self.subTest(key=key, value=value):
                token = jwt.encode(
                    {**payload, key: value}, self.settings.secret_key,
                    algorithm="HS256", headers={"typ": "at+jwt"},
                )
                with self.assertRaises(jwt.InvalidTokenError):
                    decode_token(token, self.settings, expected_type="access")
        for key in ("exp", "sub", "sid", "jti", "type", "iss", "aud", "iat", "nbf"):
            with self.subTest(missing=key):
                without_claim = {name: value for name, value in payload.items() if name != key}
                token = jwt.encode(without_claim, self.settings.secret_key, algorithm="HS256")
                with self.assertRaises(jwt.InvalidTokenError):
                    decode_token(token, self.settings, expected_type="access")

    def test_renewal_expiry_is_absolute_and_access_is_capped_to_it(self):
        deadline = datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=60)
        pair = create_token_pair(self.user_id, self.session_id, self.settings, refresh_expires_at=deadline)
        access = decode_token(pair.access_token, self.settings, expected_type="access")
        refresh = decode_token(pair.refresh_token, self.settings, expected_type="refresh")
        self.assertEqual(access.expires_at, deadline)
        self.assertEqual(refresh.expires_at, deadline)
        with self.assertRaises(ValueError):
            create_token_pair(self.user_id, self.session_id, self.settings, refresh_expires_at=datetime.now())

    def test_configuration_rejects_missing_key_and_invalid_lifetimes_without_exposing_the_key(self):
        for value in ("", "short"):
            with self.subTest(key_length=len(value)), self.assertRaises(ValueError):
                JWTSettings(secret_key=value)
        with self.assertRaises(ValueError):
            replace(self.settings, access_ttl_seconds=0)
        with self.assertRaises(ValueError):
            replace(self.settings, access_ttl_seconds=604800)
        self.assertNotIn(self.settings.secret_key, repr(self.settings))

    def test_jwt_configuration_uses_process_environment_over_dotenv(self):
        file_key, process_key = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        with patch("app.core.config.dotenv_values", return_value={"JWT_SECRET_KEY": file_key}), patch.dict(
            "os.environ", {"JWT_SECRET_KEY": process_key, "JWT_ACCESS_TTL_SECONDS": "600"}, clear=True,
        ):
            settings = get_jwt_settings()
        self.assertEqual(settings.secret_key, process_key)
        self.assertEqual(settings.access_ttl_seconds, 600)
        self.assertEqual(settings.refresh_ttl_seconds, 604800)

    def test_auth_configuration_fails_without_a_signing_secret(self):
        with patch("app.core.config.dotenv_values", return_value={}), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "JWT_SECRET_KEY"):
                get_jwt_settings()

    def test_bearer_dependency_requires_an_access_token_and_exposes_openapi_scheme(self):
        app = FastAPI()
        app.dependency_overrides[get_jwt_settings] = lambda: self.settings

        @app.get("/claims-only-test")
        def claims_only_test(claims: TokenClaims = Depends(get_access_claims)):
            return {"user_id": str(claims.user_id)}

        with TestClient(app) as client:
            for authorization in (None, "Basic invalid", "Bearer malformed", f"Bearer {self.pair.refresh_token}"):
                headers = {"Authorization": authorization} if authorization else {}
                response = client.get("/claims-only-test", headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["www-authenticate"], "Bearer")
            response = client.get("/claims-only-test", headers={"Authorization": f"Bearer {self.pair.access_token}"})
            self.assertEqual(response.json(), {"user_id": str(self.user_id)})
            scheme = client.get("/openapi.json").json()["components"]["securitySchemes"]["JWTBearer"]
            self.assertEqual(scheme["scheme"], "bearer")


class TokenSessionTests(unittest.TestCase):
    """SQLite proves lifecycle logic; concurrency still needs PostgreSQL tests."""

    def setUp(self):
        self.settings = JWTSettings(secret_key=secrets.token_urlsafe(48))
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine, tables=[User.__table__, AuthSession.__table__])
        self.session = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        self.user_id = uuid4()
        with self.session.begin():
            self.session.add(User(id=self.user_id, status=UserStatus.ACTIVE, role=UserRole.STUDENT))
        with self.session.begin():
            self.pair = issue_login_tokens(self.session, self.user_id, self.settings)
        self.claims = decode_token(self.pair.refresh_token, self.settings, expected_type="refresh")

    def test_login_stores_only_refresh_digest_and_access_checks_live_user_role(self):
        with self.session.begin():
            record = self.session.get(AuthSession, self.claims.session_id)
            self.assertEqual(record.refresh_token_hash, hash_refresh_token(self.pair.refresh_token))
            self.assertNotIn(self.pair.refresh_token, record.refresh_token_hash)
            self.session.get(User, self.user_id).role = UserRole.TUTOR
            user = get_authenticated_user(self.session, self.pair.access_token, self.settings)
            self.assertEqual(user.role, UserRole.TUTOR)

    def test_refresh_rotates_and_keeps_session_deadline_and_family(self):
        with self.session.begin():
            result = renew_tokens(self.session, self.pair.refresh_token, self.settings)
            self.assertIsNone(result.error)
            self.assertIsNotNone(result.tokens)
            refreshed = decode_token(result.tokens.refresh_token, self.settings, expected_type="refresh")
            self.assertEqual(refreshed.session_id, self.claims.session_id)
            self.assertEqual(refreshed.expires_at, self.claims.expires_at)
            self.assertNotEqual(refreshed.token_id, self.claims.token_id)
        with self.session.begin():
            self.assertEqual(self.session.scalar(select(func.count()).select_from(AuthSession)), 1)
            record = self.session.get(AuthSession, self.claims.session_id)
            self.assertEqual(record.refresh_token_hash, hash_refresh_token(result.tokens.refresh_token))
            self.assertEqual(get_authenticated_user(self.session, result.tokens.access_token, self.settings).id, self.user_id)

    def test_reused_old_refresh_revokes_the_entire_family_after_commit(self):
        with self.session.begin():
            fresh = renew_tokens(self.session, self.pair.refresh_token, self.settings).tokens
        with self.session.begin():
            reused = renew_tokens(self.session, self.pair.refresh_token, self.settings)
            self.assertEqual(reused.error, "reused")
            self.assertIsNone(reused.tokens)
        # Denial was committed; a new request can no longer use the newer pair.
        with self.session.begin():
            with self.assertRaises(jwt.InvalidTokenError):
                get_authenticated_user(self.session, fresh.access_token, self.settings)
            self.assertEqual(renew_tokens(self.session, fresh.refresh_token, self.settings).error, "revoked")

    def test_wrong_type_or_signature_cannot_rotate_a_session(self):
        with self.session.begin():
            for token in (self.pair.access_token, "malformed"):
                result = renew_tokens(self.session, token, self.settings)
                self.assertEqual(result.error, "invalid")
                self.assertIsNone(result.tokens)
            self.assertEqual(
                self.session.get(AuthSession, self.claims.session_id).refresh_token_hash,
                hash_refresh_token(self.pair.refresh_token),
            )

    def test_logout_is_scoped_idempotent_and_invalidates_access_and_refresh(self):
        with self.session.begin():
            revoke_token_session(self.session, self.claims.session_id, uuid4())
            self.assertIsNone(self.session.get(AuthSession, self.claims.session_id).revoked_at)
            revoke_token_session(self.session, self.claims.session_id, self.user_id)
            revoke_token_session(self.session, self.claims.session_id, self.user_id)
        with self.session.begin():
            with self.assertRaises(jwt.InvalidTokenError):
                get_authenticated_user(self.session, self.pair.access_token, self.settings)
            self.assertEqual(renew_tokens(self.session, self.pair.refresh_token, self.settings).error, "revoked")

    def test_suspended_user_is_denied_and_refresh_revokes_session(self):
        with self.session.begin():
            self.session.get(User, self.user_id).status = UserStatus.SUSPENDED
            with self.assertRaises(PermissionError):
                get_authenticated_user(self.session, self.pair.access_token, self.settings)
            self.assertEqual(renew_tokens(self.session, self.pair.refresh_token, self.settings).error, "user_inactive")
        with self.session.begin():
            self.assertIsNotNone(self.session.get(AuthSession, self.claims.session_id).revoked_at)

    def test_db_session_expiry_is_checked_even_for_a_still_valid_signed_jwt(self):
        with self.session.begin():
            self.session.get(AuthSession, self.claims.session_id).expires_at = datetime.now(UTC) - timedelta(seconds=1)
            # Move creation as well to preserve the lifetime constraint.
            self.session.get(AuthSession, self.claims.session_id).created_at = datetime.now(UTC) - timedelta(days=1)
        with self.session.begin():
            with self.assertRaises(jwt.InvalidTokenError):
                get_authenticated_user(self.session, self.pair.access_token, self.settings)
            self.assertEqual(renew_tokens(self.session, self.pair.refresh_token, self.settings).error, "expired")

    def test_rolled_back_rotation_does_not_consume_the_old_refresh(self):
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.session.begin():
                result = renew_tokens(self.session, self.pair.refresh_token, self.settings)
                self.assertIsNotNone(result.tokens)
                raise RuntimeError("rollback")
        with self.session.begin():
            self.assertIsNotNone(renew_tokens(self.session, self.pair.refresh_token, self.settings).tokens)


if __name__ == "__main__":
    unittest.main()
