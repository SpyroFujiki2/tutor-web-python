"""Check PostgreSQL connectivity, migration version and expected tables."""

import sys
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_database_settings
from app.core.database import create_database_engine, expected_schema_heads
from app.models import Base


def main() -> None:
    engine = create_database_engine(get_database_settings())
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
            print(f"PostgreSQL connection OK; {len(Base.metadata.tables)} application tables; migration at head.")
    except SQLAlchemyError:
        raise SystemExit("Database check failed. Check credentials, host/port and migration; no credentials were printed.") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
