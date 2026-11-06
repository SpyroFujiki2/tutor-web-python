"""Check PostgreSQL connectivity, migration version and expected tables."""

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_database_settings
from app.core.database import create_database_engine, expected_schema_heads
from app.models import Base


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-supabase", action="store_true",
                        help="Reject a local or other database before opening a connection")
    args = parser.parse_args(argv)
    try:
        settings = get_database_settings()
    except ValueError:
        raise SystemExit(
            "Database configuration is invalid. Set DATABASE_URL to a complete PostgreSQL "
            "connection string; Supabase API URL/keys cannot replace it."
        ) from None
    if args.require_supabase and not settings.is_supabase:
        raise SystemExit(
            "Backend is not configured for Supabase. Copy the PostgreSQL connection "
            "string from Supabase Connect into DATABASE_URL; no connection was attempted."
        )
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
            missing = set(Base.metadata.tables) - tables
            if "alembic_version" not in tables or missing:
                raise SystemExit("Database connected but schema is missing. Run alembic upgrade head.")
            heads = frozenset(connection.scalars(text("SELECT version_num FROM alembic_version")))
            if heads != expected_schema_heads():
                raise SystemExit("Database migration is out of date. Run alembic upgrade head.")
            provider = "Supabase PostgreSQL" if settings.is_supabase else "PostgreSQL"
            print(f"{provider} connection OK; {len(Base.metadata.tables)} application tables; migration at head.")
    except SQLAlchemyError:
        raise SystemExit("Database check failed. Check credentials, host/port and migration; no credentials were printed.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
