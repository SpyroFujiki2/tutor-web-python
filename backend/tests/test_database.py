import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies.database import get_session
from app.core.config import DatabaseSettings, ROOT_DIR, Settings, get_database_settings
from app.core.database import create_session_factory
from app.main import create_app
from scripts import init_env


class DatabaseConfigurationTests(unittest.TestCase):
    def test_password_special_characters_are_preserved_without_url_interpolation(self):
        password = "example@:#%/?password"
        url = URL.create("postgresql+psycopg", username="app", password=password, host="db", port=5433, database="project")
        values = {"DATABASE_URL": url.render_as_string(hide_password=False)}
        with patch("app.core.config.dotenv_values", return_value=values), patch.dict("os.environ", {}, clear=True):
            settings = get_database_settings()
        self.assertEqual(settings.url.password, password)
        self.assertEqual(settings.url.port, 5433)
        self.assertNotIn(password, repr(settings))
        self.assertNotIn(password, str(settings.url))

    def test_process_database_url_overrides_file_url(self):
        with patch("app.core.config.dotenv_values", return_value={"DATABASE_URL": "postgresql://local:example@localhost/local"}), patch.dict(
            "os.environ", {"DATABASE_URL": "postgresql://app:example@db:5433/project"}, clear=True,
        ):
            settings = get_database_settings()
        self.assertEqual(settings.url.drivername, "postgresql+psycopg")
        self.assertEqual(settings.url.host, "db")
        self.assertEqual(settings.url.database, "project")

    def test_missing_password_or_non_postgres_url_is_rejected(self):
        for values in (
            {}, {"DATABASE_URL": "sqlite://"}, {"DATABASE_URL": "not-a-url"},
            {"DB_PASSWORD": "legacy-does-not-configure-runtime"},
            {"DATABASE_URL": "postgresql://app@db/project"},
        ):
            with self.subTest(values=values), patch("app.core.config.dotenv_values", return_value=values), patch.dict(
                "os.environ", {}, clear=True,
            ), self.assertRaises(ValueError):
                get_database_settings()

    def test_init_env_is_idempotent_and_preserves_existing_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.example").write_text("DATABASE_URL=\nJWT_SECRET_KEY=\n", encoding="utf-8")
            output = io.StringIO()
            with patch.object(init_env, "ROOT", root), patch("sys.argv", ["init_env.py", "--docker"]), patch.dict(
                "os.environ", {}, clear=True,
            ), redirect_stdout(output):
                init_env.main()
                first = dotenv_values(root / ".env")
                admin_secret = (root / ".local/postgres-admin-password").read_text(encoding="utf-8")
                init_env.main()
                second = dotenv_values(root / ".env")
            self.assertEqual(set(first), {"DATABASE_URL", "JWT_SECRET_KEY"})
            self.assertEqual((root / ".local/postgres-admin-password").read_text(encoding="utf-8"), admin_secret)
            self.assertNotIn(admin_secret, output.getvalue())
            for key in ("DATABASE_URL", "JWT_SECRET_KEY"):
                self.assertTrue(first[key])
                self.assertEqual(first[key], second[key])
                self.assertNotIn(first[key], output.getvalue())

    def test_frozen_migration_compiles_each_postgresql_enum_once(self):
        buffer = io.StringIO()
        config = Config(str(ROOT_DIR / "alembic.ini"), output_buffer=buffer)
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://app:example-test-password@localhost/test"}):
            command.upgrade(config, "head", sql=True)
        sql = buffer.getvalue()
        self.assertEqual(sql.count("CREATE TABLE "), 26)  # 25 application + alembic_version
        self.assertEqual(sql.count("CREATE TYPE "), 15)
        self.assertNotIn("example-test-password", sql)

    def test_connection_options_live_in_url_with_code_defaults(self):
        with patch("app.core.config.dotenv_values", return_value={
            "DATABASE_URL": "postgresql://app:example@localhost/test?sslmode=require&connect_timeout=8",
        }), patch.dict("os.environ", {}, clear=True):
            settings = get_database_settings()
        self.assertEqual(settings.connect_timeout, 8)
        self.assertEqual(settings.url.query["sslmode"], "require")

    def test_legacy_migration_preserves_credentials_and_customizes_port_in_url(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "DB_HOST=localhost\nDB_PORT=5432\nDB_NAME=existing\nDB_USER=existing_user\n"
                "DB_PASSWORD='example@:#%/?password'\nDB_SSLMODE=require\nDB_CONNECT_TIMEOUT=8\n"
                "PG_ADMIN_PASSWORD=old-admin-example\nJWT_SECRET_KEY=unchanged-example\n"
                "JWT_ACCESS_TTL_SECONDS=600\nJWT_ISSUER=tutor-web\n",
                encoding="utf-8",
            )
            with patch.object(init_env, "ROOT", root), patch("sys.argv", ["init_env.py", "--docker", "--db-port", "5433"]), patch.dict(
                "os.environ", {}, clear=True,
            ), redirect_stdout(io.StringIO()):
                init_env.main()
            values = dotenv_values(root / ".env")
            from app.core.config import parse_database_url
            settings = parse_database_url(values["DATABASE_URL"])
            self.assertEqual(settings.url.password, "example@:#%/?password")
            self.assertEqual(settings.url.username, "existing_user")
            self.assertEqual(settings.url.database, "existing")
            self.assertEqual(settings.url.port, 5433)
            self.assertEqual(settings.connect_timeout, 8)
            self.assertEqual(values["JWT_SECRET_KEY"], "unchanged-example")
            self.assertEqual(values["JWT_ACCESS_TTL_SECONDS"], "600")
            self.assertNotIn("JWT_ISSUER", values)
            self.assertFalse(any(key in values for key in init_env.LEGACY_KEYS))
            self.assertEqual((root / ".local/postgres-admin-password").read_text(encoding="utf-8"), "old-admin-example")

    def test_external_url_does_not_overwrite_existing_local_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("DB_PASSWORD=local-example\nJWT_SECRET_KEY=unchanged-example\n", encoding="utf-8")
            with patch.object(init_env, "ROOT", root), patch("sys.argv", ["init_env.py"]), patch.dict(
                "os.environ", {"DATABASE_URL": "postgresql://remote:external-example@remote/remote"}, clear=True,
            ), redirect_stdout(io.StringIO()):
                init_env.main()
            saved = dotenv_values(root / ".env")
            from app.core.config import parse_database_url
            self.assertEqual(parse_database_url(saved["DATABASE_URL"]).url.password, "local-example")
            self.assertNotIn("external-example", (root / ".env").read_text(encoding="utf-8"))
            self.assertFalse((root / ".local/postgres-admin-password").exists())


class DatabaseRequestTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)"))
            connection.execute(text("INSERT INTO alembic_version VALUES ('0001_initial_schema')"))
            connection.execute(text("CREATE TABLE auth_sessions (id INTEGER PRIMARY KEY)"))
        self.settings = DatabaseSettings(URL.create(
            "postgresql+psycopg", username="test", password="example", host="127.0.0.1", database="test",
        ))
        self.app = create_app(Settings(cors_origins=()), self.settings)

    def test_lifespan_wires_session_readiness_and_disposes_on_shutdown(self):
        with patch("app.main.create_database_engine", return_value=self.engine), patch.object(
            self.engine, "dispose", wraps=self.engine.dispose,
        ) as dispose:
            with TestClient(self.app) as client:
                self.assertEqual(client.get("/api/health").status_code, 200)
                self.assertEqual(client.get("/api/ready").status_code, 200)
                self.assertIsNotNone(self.app.state.session_factory)
            dispose.assert_called_once()
            self.assertIsNone(self.app.state.session_factory)

    def test_readiness_rejects_stale_migration(self):
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num='outdated'"))
        with patch("app.main.create_database_engine", return_value=self.engine), TestClient(self.app) as client:
            self.assertEqual(client.get("/api/ready").status_code, 503)
            self.assertEqual(client.get("/api/health").status_code, 200)

    def test_readiness_hides_database_errors(self):
        def failed_session():
            class BrokenSession:
                def execute(self, *_args):
                    raise OperationalError("secret SQL", {}, Exception("secret password"))
            yield BrokenSession()

        self.app.dependency_overrides[get_session] = failed_session
        response = TestClient(self.app).get("/api/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.text)

    def test_session_dependency_does_not_commit_pending_work(self):
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE pending_work (id INTEGER PRIMARY KEY)"))
        factory = create_session_factory(self.engine)
        with factory() as session:
            session.execute(text("INSERT INTO pending_work VALUES (1)"))
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(text("SELECT COUNT(*) FROM pending_work")), 0)


if __name__ == "__main__":
    unittest.main()
