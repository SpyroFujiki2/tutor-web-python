import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import URL
from sqlalchemy.exc import OperationalError
from alembic import command
from alembic.config import Config

from app.core.config import ROOT_DIR, DatabaseSettings, get_database_settings, parse_database_url
from app.models import Base
from scripts import bootstrap_db, check_db


class SupabaseConfigurationTests(unittest.TestCase):
    def test_migrations_enable_rls_on_every_application_table_and_version_table(self):
        output = io.StringIO()
        config = Config(str(ROOT_DIR / "alembic.ini"), output_buffer=output)
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://app:example@localhost/test"}):
            command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        for table in (*Base.metadata.tables, "alembic_version"):
            self.assertIn(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY', sql)
        self.assertNotIn("CREATE POLICY", sql)
        self.assertNotIn("ALTER TABLE auth.", sql)
        self.assertNotIn("ALTER TABLE storage.", sql)

    def test_pooler_connection_defaults_to_ssl_without_changing_credentials(self):
        password = "example@:#%/?password"
        url = URL.create("postgresql", username="postgres.project", password=password,
                         host="aws-0-example.pooler.supabase.com", port=6543, database="postgres")
        settings = parse_database_url(url.render_as_string(hide_password=False))
        self.assertTrue(settings.is_supabase)
        self.assertEqual(settings.url.drivername, "postgresql+psycopg")
        self.assertEqual(settings.url.password, password)
        self.assertEqual(settings.url.query["sslmode"], "require")
        self.assertNotIn(password, repr(settings))
        self.assertNotIn(password, str(settings.url))

    def test_direct_connection_keeps_explicit_certificate_verification(self):
        settings = parse_database_url(
            "postgres://postgres:example@db.project.supabase.co:5432/postgres"
            "?sslmode=verify-full&sslrootcert=server.crt&connect_timeout=8"
        )
        self.assertTrue(settings.is_supabase)
        self.assertEqual(settings.url.query["sslmode"], "verify-full")
        self.assertEqual(settings.url.query["sslrootcert"], "server.crt")
        self.assertEqual(settings.connect_timeout, 8)

    def test_supabase_does_not_allow_plaintext_or_opportunistic_ssl(self):
        for mode in ("disable", "allow", "prefer"):
            with self.subTest(mode=mode), self.assertRaises(ValueError) as error:
                parse_database_url(
                    "postgresql://postgres:secret-placeholder@db.project.supabase.co/postgres"
                    f"?sslmode={mode}"
                )
            self.assertNotIn("secret-placeholder", str(error.exception))

    def test_other_hosts_do_not_get_supabase_defaults(self):
        for host in ("localhost", "project.supabase.co.example.com"):
            with self.subTest(host=host):
                settings = parse_database_url(f"postgresql://app:example@{host}/project")
                self.assertFalse(settings.is_supabase)
                self.assertNotIn("sslmode", settings.url.query)

    def test_local_env_overrides_base_and_process_overrides_both_without_reading_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("DATABASE_URL=postgresql://base:example@localhost/base\n", encoding="utf-8")
            (root / ".env.local").write_text(
                "DATABASE_URL=postgresql://postgres.project:example@pooler.supabase.com:6543/postgres\n",
                encoding="utf-8-sig",
            )
            (root / ".env.seed").write_text("DATABASE_URL=postgresql://seed:example@localhost/seed\n", encoding="utf-8")
            with patch("app.core.config.ROOT_DIR", root), patch.dict(os.environ, {}, clear=True):
                self.assertEqual(get_database_settings().url.username, "postgres.project")
                with patch.dict(os.environ, {"DATABASE_URL": "postgresql://process:example@localhost/process"}):
                    self.assertEqual(get_database_settings().url.username, "process")

    def test_public_api_settings_are_not_used_as_database_credentials(self):
        values = {"VITE_SUPABASE_URL": "https://project.supabase.co",
                  "VITE_SUPABASE_PUBLISHABLE_KEY": "sb_publishable_example"}
        with patch("app.core.config.dotenv_values", return_value=values), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "PostgreSQL connection string"):
                get_database_settings()

    def test_supabase_check_rejects_local_configuration_without_connecting(self):
        settings = parse_database_url("postgresql://app:example@localhost/project")
        with patch.object(check_db, "get_database_settings", return_value=settings), patch.object(
            check_db, "create_database_engine"
        ) as create:
            with self.assertRaisesRegex(SystemExit, "not configured for Supabase"):
                check_db.main(["--require-supabase"])
        create.assert_not_called()

    def test_failed_supabase_connection_never_falls_back_to_local_administrator_bootstrap(self):
        settings = DatabaseSettings(URL.create(
            "postgresql+psycopg", username="postgres.project", password="secret-placeholder",
            host="pooler.supabase.com", port=6543, database="postgres",
        ))
        engine = MagicMock()
        engine.connect.side_effect = OperationalError("private SQL", {}, Exception("secret-placeholder"))
        with patch.object(bootstrap_db, "get_database_settings", return_value=settings), patch.object(
            bootstrap_db, "create_database_engine", return_value=engine
        ), patch.object(bootstrap_db.getpass, "getpass") as prompt, patch.object(
            bootstrap_db.psycopg, "connect"
        ) as admin_connect, patch("sys.argv", ["bootstrap_db.py"]):
            with self.assertRaisesRegex(SystemExit, "local administrator bootstrap was not attempted") as error:
                bootstrap_db.main()
        self.assertNotIn("secret-placeholder", str(error.exception))
        prompt.assert_not_called()
        admin_connect.assert_not_called()
        engine.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
