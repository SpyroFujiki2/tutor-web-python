import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

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
