"""[UI] HTTP API = the project's "custom webhook". Same service as the UI.

    POST /api/profiles            body ProfileRequest      -> 201 UserProfile
    GET  /api/profiles/{id}                                -> 200 UserProfile
    POST /api/recommendations     body RecommendRequest    -> 200 RecommendationRun
                                  (status ok | closest_only | no_match; 502 when status=error)
    GET  /api/runs?profile_id=                             -> 200 [RunSummary]
    GET  /api/runs/{id}                                    -> 200 RecommendationRun
    GET  /api/catalog/stats                                -> 200 CatalogStats
    GET  /api/health                                       -> 200 {"ok": true, ...}

Errors always use contracts.ErrorResponse with its own http_status
(400 invalid input, 404 unknown id, 409 conflict, 5xx upstream/internal).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..config import Settings, load_settings
from ..contracts.errors import ErrorResponse, GameGeneError
from ..contracts.models import (
    CatalogStats,
    ProfileRequest,
    RecommendationRun,
    RecommendRequest,
    RunStatus,
    RunSummary,
    UserProfile,
)
from ..contracts.protocols import GameGeneService
from .service import make_service


def create_app(
    service: GameGeneService | None = None,
    settings: Settings | None = None,
    *,
    with_ui: bool = True,
) -> FastAPI:
    settings = settings or load_settings()
    service = service or make_service(settings)
    app = FastAPI(title="Game Gene Agent API", version="1.0")

    @app.exception_handler(GameGeneError)
    async def _domain_error(_: Request, err: GameGeneError) -> JSONResponse:
        body = err.to_response()
        return JSONResponse(body.model_dump(mode="json"), status_code=body.http_status)

    @app.exception_handler(RequestValidationError)
    async def _bad_body(_: Request, err: RequestValidationError) -> JSONResponse:
        problems = [
            f"{'.'.join(str(p) for p in e['loc'][1:]) or 'body'}: {e['msg']}" for e in err.errors()
        ]
        body = ErrorResponse(
            code="invalid_input",
            message="request body is malformed",
            http_status=400,
            details={"problems": problems},
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=400)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "service": settings.service, "catalog": settings.catalog_source}

    @app.post("/api/profiles", status_code=201, response_model=UserProfile)
    def post_profile(request: ProfileRequest) -> UserProfile:
        return service.build_profile(request)

    @app.get("/api/profiles/{profile_id}", response_model=UserProfile)
    def get_profile(profile_id: str) -> UserProfile:
        return service.get_profile(profile_id)

    @app.post("/api/recommendations", response_model=RecommendationRun)
    def post_recommendation(request: RecommendRequest):
        run = service.recommend(request)
        if run.status == RunStatus.ERROR:
            return JSONResponse(run.model_dump(mode="json"), status_code=502)
        return run

    @app.get("/api/runs", response_model=list[RunSummary])
    def list_runs(profile_id: str | None = None) -> list[RunSummary]:
        return service.list_runs(profile_id)

    @app.get("/api/runs/{run_id}", response_model=RecommendationRun)
    def get_run(run_id: str) -> RecommendationRun:
        return service.get_run(run_id)

    @app.get("/api/catalog/stats", response_model=CatalogStats)
    def catalog_stats() -> CatalogStats:
        return service.catalog_stats()

    if with_ui:
        import gradio as gr

        from .ui import build_ui

        app = gr.mount_gradio_app(app, build_ui(service, settings), path="/")
    return app
