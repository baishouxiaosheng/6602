"""Structured errors shared by every workflow.

Rule (course Lec 9): every failure must end somewhere a person can see it.
Raise one of these; the service boundary (Gradio handler / FastAPI) converts it
with ``to_response()``. Never let a bare exception or a silent ``None`` escape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    ok: bool = False
    code: str
    message: str
    http_status: int
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class GameGeneError(Exception):
    """Base class. ``code`` is stable and machine-readable; ``message`` is for people."""

    code = "internal_error"
    http_status = 500
    retryable = False

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            code=self.code,
            message=self.message,
            http_status=self.http_status,
            retryable=self.retryable,
            details=self.details,
        )


class InvalidInput(GameGeneError):
    """Deterministic validation failed BEFORE any Steam or model call (test 2)."""

    code = "invalid_input"
    http_status = 400


class NotFound(GameGeneError):
    """A profile / run / game id does not exist in the store."""

    code = "not_found"
    http_status = 404


class Conflict(GameGeneError):
    """Duplicate request_id or stale revision (duplicate control, Lec 6)."""

    code = "conflict"
    http_status = 409


class UnsupportedMode(GameGeneError):
    """Request matched no route (test 3, 'no matching path')."""

    code = "unsupported_mode"
    http_status = 422


class UpstreamError(GameGeneError):
    """Steam / retrieval / model endpoint failed or timed out. Retry may succeed."""

    code = "upstream_error"
    http_status = 502
    retryable = True


class RateLimited(UpstreamError):
    code = "rate_limited"
    http_status = 429


class SteamProfilePrivate(GameGeneError):
    """GetOwnedGames returned an empty response: profile or game details are private."""

    code = "steam_profile_private"
    http_status = 403


class LLMOutputInvalid(GameGeneError):
    """Model answered, but the answer never passed schema validation after retries.

    ``details`` carries ``model`` and ``raw_head`` (first 200 chars), as in Lec 9.
    """

    code = "llm_output_invalid"
    http_status = 502


class StorageError(GameGeneError):
    code = "storage_error"
    http_status = 500


class ConfigError(GameGeneError):
    code = "config_error"
    http_status = 500
