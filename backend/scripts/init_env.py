"""Initialize a minimal .env; migrate old DB_* settings without changing credentials."""

import argparse
import os
import secrets
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values, set_key, unset_key
from sqlalchemy import URL

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import parse_database_url

ROOT = Path(__file__).resolve().parents[2]
LEGACY_KEYS = (
    "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSLMODE",
    "DB_CONNECT_TIMEOUT", "PG_ADMIN_USER", "PG_ADMIN_PASSWORD",
)
OPTIONAL_DEFAULTS = {
    "VITE_API_BASE_URL": "http://localhost:8000", "JWT_ISSUER": "tutor-web",
    "JWT_AUDIENCE": "tutor-web-api", "JWT_ACCESS_TTL_SECONDS": "900",
    "JWT_REFRESH_TTL_SECONDS": "604800",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", action="store_true", help="Initialize a private Docker admin password file")
    parser.add_argument("--db-port", type=int, help="Update the port inside DATABASE_URL")
    args = parser.parse_args()
    if args.db_port is not None and not 1 <= args.db_port <= 65535:
        parser.error("--db-port must be between 1 and 65535")
    if args.db_port is not None and os.getenv("DATABASE_URL"):
        parser.error("Set the port in the process DATABASE_URL instead of using --db-port")
    env_path = ROOT / ".env"
    if not env_path.exists():
        shutil.copyfile(ROOT / ".env.example", env_path)
    file_values = dotenv_values(env_path)
    values = {**file_values, **os.environ}
    local_database = bool(file_values.get("DATABASE_URL")) or any(
        file_values.get(key) for key in LEGACY_KEYS if key.startswith("DB_")
    )
    source = file_values if local_database else values
    if source.get("DATABASE_URL"):
        url = parse_database_url(source["DATABASE_URL"]).url
    else:
        query = {}
        if source.get("DB_SSLMODE") and source["DB_SSLMODE"] != "prefer":
            query["sslmode"] = source["DB_SSLMODE"]
        if source.get("DB_CONNECT_TIMEOUT") and source["DB_CONNECT_TIMEOUT"] != "5":
            query["connect_timeout"] = source["DB_CONNECT_TIMEOUT"]
        url = URL.create(
            "postgresql+psycopg", username=source.get("DB_USER") or "tutor_app",
            password=source.get("DB_PASSWORD") or secrets.token_urlsafe(32),
            host=source.get("DB_HOST") or "127.0.0.1", port=int(source.get("DB_PORT") or "5432"),
            database=source.get("DB_NAME") or "tutor_web", query=query,
        )
    if args.db_port is not None:
        url = url.set(port=args.db_port)
    # Validate BEFORE editing configuration; URL rendering percent-encodes credentials.
    parse_database_url(url.render_as_string(hide_password=False))
    if local_database or not os.getenv("DATABASE_URL"):
        set_key(str(env_path), "DATABASE_URL", url.render_as_string(hide_password=False), quote_mode="auto")
    if not values.get("JWT_SECRET_KEY"):
        set_key(str(env_path), "JWT_SECRET_KEY", secrets.token_urlsafe(48), quote_mode="auto")
    if args.docker:
        secret_path = ROOT / ".local" / "postgres-admin-password"
        if not secret_path.exists():
            secret_path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve the old Docker administrator credential when migrating an existing volume.
            secret_path.write_text(values.get("PG_ADMIN_PASSWORD") or secrets.token_urlsafe(32), encoding="utf-8")
        if os.name != "nt":
            secret_path.chmod(0o600)
    for key in LEGACY_KEYS:
        if key in file_values:
            unset_key(str(env_path), key)
    for key, default in OPTIONAL_DEFAULTS.items():
        if file_values.get(key) == default:
            unset_key(str(env_path), key)
    if os.name != "nt":
        env_path.chmod(0o600)
    print("Local .env uses DATABASE_URL; existing credentials were preserved and not printed.")


if __name__ == "__main__":
    main()
