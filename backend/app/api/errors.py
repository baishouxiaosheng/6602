from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.adapters.http import UpstreamHttpError
from app.adapters.steam.identity import InvalidSteamIdentity
from app.services.errors import ServiceError


class ApiError(BaseModel):
    ok: bool = False
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    payload = ApiError(
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        details=exc.details,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    payload = ApiError(
        code="invalid_input",
        message="Request validation failed.",
        details={"problems": exc.errors()},
    )
    return JSONResponse(status_code=400, content=payload.model_dump(mode="json"))


async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    payload = ApiError(
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
    )
    status_code = 404 if exc.code == "not_found" else 400
    if exc.code == "configuration_unavailable":
        status_code = 503
    return JSONResponse(status_code=status_code, content=payload.model_dump())


async def upstream_error_handler(_: Request, exc: UpstreamHttpError) -> JSONResponse:
    payload = ApiError(
        code="upstream_error",
        message=str(exc),
        retryable=exc.retryable,
    )
    return JSONResponse(status_code=502, content=payload.model_dump())


async def invalid_steam_identity_handler(
    _: Request, exc: InvalidSteamIdentity
) -> JSONResponse:
    payload = ApiError(code="invalid_steam_identity", message=str(exc))
    return JSONResponse(status_code=400, content=payload.model_dump())


async def unexpected_error_handler(_: Request, __: Exception) -> JSONResponse:
    payload = ApiError(
        code="internal_error",
        message="The request could not be completed.",
    )
    return JSONResponse(status_code=500, content=payload.model_dump())
