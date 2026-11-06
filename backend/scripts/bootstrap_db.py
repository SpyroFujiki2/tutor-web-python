"""Create only the project role/database; never reset an existing role password."""

import argparse
import getpass
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import ROOT_DIR, get_database_settings
from app.core.database import create_database_engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true")
    parser.add_argument("--admin-user", default="postgres")
    args = parser.parse_args()
    settings = get_database_settings()
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            if connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")):
                raise SystemExit("Use a dedicated non-superuser account in DATABASE_URL.")
        print("Existing project DB connection verified; administrator credentials are not needed.")
        return
    except SQLAlchemyError:
        if settings.is_supabase:
            raise SystemExit(
                "Supabase connection failed. Check DATABASE_URL in .env/.env.local "
                "or the process environment. Hosted databases must be provisioned in "
                "Supabase; local administrator bootstrap was not attempted."
            ) from None
    finally:
        engine.dispose()
    admin_password = os.getenv("PG_ADMIN_PASSWORD")
    if args.docker:
        secret_path = ROOT_DIR / ".local" / "postgres-admin-password"
        if not secret_path.exists():
            raise SystemExit("Run init_env.py --docker before Docker database setup.")
        admin_password = secret_path.read_text(encoding="utf-8").rstrip("\r\n")
    if not admin_password:
        if not sys.stdin.isatty():
            raise SystemExit("Run setup in an interactive terminal to enter the existing PostgreSQL admin password.")
        admin_password = getpass.getpass("Existing PostgreSQL admin password (hidden): ")
    try:
        with psycopg.connect(
            host=settings.url.host, port=settings.url.port or 5432, dbname="postgres",
            user=args.admin_user, password=admin_password,
            connect_timeout=settings.connect_timeout,
            sslmode=settings.url.query.get("sslmode", "prefer"), autocommit=True,
        ) as connection:
            role, database = settings.url.username, settings.url.database
            existing_db = connection.execute(
                "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (database,),
            ).fetchone()
            if existing_db is not None and existing_db[0] != role:
                raise SystemExit("Existing database has another owner; select a different database/user in DATABASE_URL.")
            existing_role = connection.execute(
                "SELECT rolcanlogin, rolsuper FROM pg_roles WHERE rolname = %s", (role,),
            ).fetchone()
            if existing_role is None:
                connection.execute(sql.SQL(
                    "CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                ).format(sql.Identifier(role), sql.Literal(settings.url.password)))
                print("Created the project login role.")
            elif not existing_role[0] or existing_role[1]:
                raise SystemExit("Use a dedicated non-superuser login in DATABASE_URL.")
            if existing_db is None:
                connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database), sql.Identifier(role),
                ))
                connection.execute(sql.SQL("ALTER DATABASE {} SET timezone TO 'UTC'").format(sql.Identifier(database)))
                print("Created the project database with UTC timezone.")
        engine = create_database_engine(settings)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except (psycopg.Error, SQLAlchemyError):
        # Do not expose SQL, URLs, passwords or server messages.
        raise SystemExit("Database setup/connection failed. Check local credentials, port and ownership.") from None
    print("Project DB connection verified. Next: python -m alembic -c alembic.ini upgrade head")


if __name__ == "__main__":
    main()
