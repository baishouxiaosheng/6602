from functools import partial

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.api.dependencies import ServicesDependency
from app.domain.enums import JobType
from app.domain.jobs import Job
from app.domain.profiles import (
    SteamImportConfirmRequest,
    SteamImportPreview,
    SteamImportPreviewRequest,
)

router = APIRouter(tags=["steam-import"])


class SteamPreviewResponse(BaseModel):
    ok: bool = True
    preview: SteamImportPreview


class JobResponse(BaseModel):
    ok: bool = True
    job: Job


@router.post(
    "/profiles/{profile_id}/steam-import/preview",
    response_model=SteamPreviewResponse,
)
async def preview_steam_import(
    profile_id: str,
    request: SteamImportPreviewRequest,
    services: ServicesDependency,
) -> SteamPreviewResponse:
    preview = await services.steam_import.preview(profile_id, request)
    return SteamPreviewResponse(preview=preview)


@router.post(
    "/profiles/{profile_id}/steam-import/confirm",
    response_model=JobResponse,
    status_code=202,
)
async def confirm_steam_import(
    profile_id: str,
    request: SteamImportConfirmRequest,
    background_tasks: BackgroundTasks,
    services: ServicesDependency,
) -> JobResponse:
    job = services.jobs.create(JobType.STEAM_IMPORT)
    worker = partial(services.steam_import.confirm, profile_id, request)
    background_tasks.add_task(services.jobs.run, job.job_id, worker)
    return JobResponse(job=job)
