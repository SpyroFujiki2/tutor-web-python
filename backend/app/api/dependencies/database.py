from collections.abc import Generator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Generator[Session, None, None]:
    """One Session per request; no implicit commit. Caller owns the transaction."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        raise HTTPException(status_code=503, detail="Database is not available")
    with factory() as session:
        yield session
    # close() rolls back uncommitted changes, including on exceptions.
