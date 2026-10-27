from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import DatabaseSettings, Settings, get_database_settings, get_settings
from app.core.database import create_database_engine, create_session_factory


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

    application = FastAPI(title="Tutor Web API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )
    application.include_router(api_router, prefix="/api")
    return application


app = create_app()
