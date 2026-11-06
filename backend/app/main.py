from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.router import api_router
from app.core.config import DatabaseSettings, Settings, get_database_settings, get_settings
from app.core.database import create_database_engine, create_session_factory
from app.core.rate_limit import LoginRateLimiter
from app.modules.common import RateLimitError

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None, database_settings: DatabaseSettings | None = None,
) -> FastAPI:
    settings = settings if settings is not None else get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        engine = create_database_engine(database_settings or get_database_settings())
        application.state.engine = engine
        application.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()
            application.state.session_factory = None

    application = FastAPI(
        title="Tutor Web API", version="0.1.0", lifespan=lifespan,
        docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json",
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
    )
    application.state.login_rate_limiter = LoginRateLimiter()
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )
    application.include_router(api_router, prefix="/api")

    @application.exception_handler(LookupError)
    async def not_found(_request, error):
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @application.exception_handler(PermissionError)
    async def forbidden(_request, error):
        return JSONResponse(status_code=403, content={"detail": str(error)})

    @application.exception_handler(ValueError)
    async def invalid_operation(_request, error):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    @application.exception_handler(RateLimitError)
    async def rate_limited(_request, error):
        return JSONResponse(status_code=429, content={"detail": str(error)}, headers={"Retry-After": "60"})

    @application.exception_handler(IntegrityError)
    async def conflict(_request, _error):
        return JSONResponse(status_code=409, content={"detail": "Dữ liệu trùng hoặc đã thay đổi; hãy tải lại."})

    @application.exception_handler(SQLAlchemyError)
    async def unavailable(_request, error):
        logger.error("Database request failed (%s)", type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "Cơ sở dữ liệu tạm thời không khả dụng."})

    @application.middleware("http")
    async def private_response(request, call_next):
        response = await call_next(request)
        if request.headers.get("authorization") or request.url.path.startswith("/api/auth"):
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    return application


app = create_app()
