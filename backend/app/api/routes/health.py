from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.database import get_session
from app.core.database import expected_schema_heads

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", message="FastAPI đang hoạt động")


@router.get("/ready", response_model=HealthResponse)
def readiness_check(session: Annotated[Session, Depends(get_session)]) -> HealthResponse:
    try:
        session.execute(text("SELECT 1"))
        heads = frozenset(session.scalars(text("SELECT version_num FROM alembic_version")))
        if heads != expected_schema_heads():
            raise HTTPException(status_code=503, detail="Database migrations are not up to date")
        session.execute(text("SELECT 1 FROM auth_sessions LIMIT 0"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database is not ready") from None
    return HealthResponse(status="ok", message="PostgreSQL đã kết nối và có schema")
