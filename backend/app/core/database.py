"""Engine/Session factory; schema changes are applied separately by Alembic."""

from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import ROOT_DIR, DatabaseSettings


def create_database_engine(settings: DatabaseSettings) -> Engine:
    return create_engine(
        settings.url, pool_pre_ping=True, pool_timeout=5, echo=False, hide_parameters=True,
        connect_args={"connect_timeout": settings.connect_timeout, "options": "-c timezone=UTC"},
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def expected_schema_heads() -> frozenset[str]:
    config = Config(str(ROOT_DIR / "alembic.ini"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())
