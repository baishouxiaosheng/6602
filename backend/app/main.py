from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.http import UpstreamHttpError
from app.adapters.steam.identity import InvalidSteamIdentity
from app.api.catalog import router as catalog_router
from app.api.errors import (
    AppError,
    app_error_handler,
    invalid_steam_identity_handler,
    service_error_handler,
    unexpected_error_handler,
    upstream_error_handler,
    validation_error_handler,
)
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.profiles import router as profiles_router
from app.api.questionnaire import router as questionnaire_router
from app.api.recommendations import router as recommendations_router
from app.api.steam_import import router as steam_import_router
from app.config import get_settings
from app.services.errors import ServiceError


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    services = getattr(app.state, "services", None)
    if services is not None:
        if services.http_client is not None:
            await services.http_client.aclose()
        services.database.engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Evidence-grounded Steam game recommendation API.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(UpstreamHttpError, upstream_error_handler)
    app.add_exception_handler(InvalidSteamIdentity, invalid_steam_identity_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
    app.include_router(health_router, prefix="/api")
    app.include_router(questionnaire_router, prefix="/api")
    app.include_router(profiles_router, prefix="/api")
    app.include_router(steam_import_router, prefix="/api")
    app.include_router(jobs_router, prefix="/api")
    app.include_router(recommendations_router, prefix="/api")
    app.include_router(catalog_router, prefix="/api")
    return app


app = create_app()
