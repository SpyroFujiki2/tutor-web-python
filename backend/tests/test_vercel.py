import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sqlalchemy import URL

from app.core.config import BACKEND_DIR, DatabaseSettings
from app.core.database import create_database_engine, expected_schema_heads, set_transaction_timezone


class VercelDeploymentTests(unittest.TestCase):
    def test_schema_heads_work_from_an_isolated_backend_without_root_alembic_config(self):
        expected = expected_schema_heads()
        with tempfile.TemporaryDirectory() as directory:
            backend = Path(directory)
            shutil.copytree(BACKEND_DIR / "migrations", backend / "migrations",
                            ignore=shutil.ignore_patterns("__pycache__"))
            self.assertFalse((backend.parent / "alembic.ini").exists())
            expected_schema_heads.cache_clear()
            try:
                with patch("app.core.database.BACKEND_DIR", backend):
                    self.assertEqual(expected_schema_heads(), expected)
            finally:
                expected_schema_heads.cache_clear()

    def test_serverless_transaction_pool_uses_small_pool_without_prepared_or_startup_options(self):
        settings = DatabaseSettings(URL.create(
            "postgresql+psycopg", username="app.project", password="test-password",
            host="test.pooler.supabase.com", port=6543, database="postgres",
            query={"sslmode": "require"},
        ))
        with patch.dict(os.environ, {"VERCEL": "1"}), patch("app.core.database.create_engine") as create, patch(
            "app.core.database.event.listen"
        ) as listen:
            engine = create_database_engine(settings)
        options = create.call_args.kwargs
        self.assertEqual(options["pool_size"], 1)
        self.assertEqual(options["max_overflow"], 0)
        self.assertEqual(options["connect_args"], {"connect_timeout": 5, "prepare_threshold": None})
        self.assertTrue(options["hide_parameters"])
        self.assertEqual(create.call_args.args[0].query["sslmode"], "require")
        listen.assert_called_once_with(engine, "begin", set_transaction_timezone)
        connection = Mock()
        set_transaction_timezone(connection)
        connection.exec_driver_sql.assert_called_once_with("SET LOCAL TIME ZONE 'UTC'")

    def test_standalone_database_retains_session_timezone_and_default_pool(self):
        settings = DatabaseSettings(URL.create(
            "postgresql+psycopg", username="app", password="test-password",
            host="localhost", port=5432, database="project",
        ))
        with patch.dict(os.environ, {}, clear=True), patch("app.core.database.create_engine") as create:
            create_database_engine(settings)
        self.assertEqual(create.call_args.kwargs["connect_args"],
                         {"connect_timeout": 5, "options": "-c timezone=UTC"})
        self.assertNotIn("pool_size", create.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
