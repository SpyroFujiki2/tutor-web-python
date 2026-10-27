import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values
from sqlalchemy import URL, make_url
from sqlalchemy.exc import ArgumentError

ROOT_DIR = Path(__file__).resolve().parents[3]
DEFAULT_CORS_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"


def parse_cors_origins(value: str) -> tuple[str, ...]:
    origins = []
    for item in value.split(","):
        origin = item.strip().rstrip("/")
        if not origin:
            continue
        parsed = urlsplit(origin)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CORS_ORIGINS must contain HTTP(S) origins without paths.")
        # Accessing port also rejects malformed or out-of-range port values.
        parsed.port
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


@dataclass(frozen=True)
class Settings:
    cors_origins: tuple[str, ...]


def get_settings() -> Settings:
    # The process environment takes precedence without mutating os.environ.
    values = {**dotenv_values(ROOT_DIR / ".env"), **os.environ}
    cors_origins = values.get("CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    if cors_origins is None:
        cors_origins = ""
    return Settings(cors_origins=parse_cors_origins(cors_origins))


@dataclass(frozen=True)
class JWTSettings:
    secret_key: str = field(repr=False)
    issuer: str = "tutor-web"
    audience: str = "tutor-web-api"
    access_ttl_seconds: int = 900
    refresh_ttl_seconds: int = 604800

    def __post_init__(self) -> None:
        if len(self.secret_key.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 bytes")
        if not self.issuer.strip() or not self.audience.strip():
            raise ValueError("JWT issuer and audience must not be empty")
        if not 0 < self.access_ttl_seconds < self.refresh_ttl_seconds:
            raise ValueError("JWT lifetimes must satisfy 0 < access TTL < refresh TTL")


def get_jwt_settings() -> JWTSettings:
    # Read on demand: public health does not require an auth key, auth always does.
    values = {**dotenv_values(ROOT_DIR / ".env"), **os.environ}
    return JWTSettings(
        secret_key=values.get("JWT_SECRET_KEY") or "",
        issuer=values.get("JWT_ISSUER") or "tutor-web",
        audience=values.get("JWT_AUDIENCE") or "tutor-web-api",
        access_ttl_seconds=int(values.get("JWT_ACCESS_TTL_SECONDS") or "900"),
        refresh_ttl_seconds=int(values.get("JWT_REFRESH_TTL_SECONDS") or "604800"),
    )


@dataclass(frozen=True)
class DatabaseSettings:
    url: URL = field(repr=False)
    connect_timeout: int = 5

    def __post_init__(self) -> None:
        if self.url.drivername != "postgresql+psycopg":
            raise ValueError("Database must use postgresql+psycopg")
        if not self.url.host or not self.url.username or not self.url.database or not self.url.password:
            raise ValueError("Database host, user, name and password must be configured")
        if self.connect_timeout < 1:
            raise ValueError("DATABASE_URL connect_timeout must be positive")
        if self.url.port is not None and not 1 <= self.url.port <= 65535:
            raise ValueError("Database port must be between 1 and 65535")


def parse_database_url(value: str) -> DatabaseSettings:
    if not value:
        raise ValueError("DATABASE_URL must be configured")
    try:
        url = make_url(value)
        if url.drivername == "postgresql":
            url = url.set(drivername="postgresql+psycopg")
        timeout = int(url.query.get("connect_timeout", "5"))
        return DatabaseSettings(url=url, connect_timeout=timeout)
    except (ValueError, TypeError, ArgumentError):
        raise ValueError("DATABASE_URL must be a valid PostgreSQL URL with credentials and a positive timeout") from None


def get_database_settings() -> DatabaseSettings:
    values = {**dotenv_values(ROOT_DIR / ".env"), **os.environ}
    return parse_database_url(values.get("DATABASE_URL") or "")
