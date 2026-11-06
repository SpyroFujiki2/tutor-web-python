"""Engine/Session factory; schema changes are applied separately by Alembic."""

from functools import lru_cache
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import BACKEND_DIR, DatabaseSettings


def create_database_engine(settings: DatabaseSettings) -> Engine:
    # Supabase's transaction pooler does not retain per-session state and
    # cannot use Psycopg's automatic prepared statements.
    transaction_pool = settings.url.port == 6543
    transaction_timezone = transaction_pool or settings.is_supabase
    serverless = os.environ.get("VERCEL") == "1"
    connect_args = {"connect_timeout": settings.connect_timeout}
    if transaction_pool or serverless:
        connect_args["prepare_threshold"] = None
    if not transaction_timezone:
        connect_args["options"] = "-c timezone=UTC"
    pool_options = {"pool_size": 1, "max_overflow": 0} if serverless else {}
    engine = create_engine(
        settings.url, pool_pre_ping=True, pool_timeout=5, echo=False, hide_parameters=True,
        connect_args=connect_args, **pool_options,
    )
    if transaction_timezone:
        event.listen(engine, "begin", set_transaction_timezone)
    return engine


def set_transaction_timezone(connection) -> None:
    connection.exec_driver_sql("SET LOCAL TIME ZONE 'UTC'")


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def expected_schema_heads() -> frozenset[str]:
    # The deployed backend bundle has migrations but not the repository-root
    # Alembic CLI config. Read its heads without depending on the parent folder.
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())
