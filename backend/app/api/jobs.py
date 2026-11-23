from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import ServicesDependency
from app.domain.jobs import Job

router = APIRouter(tags=["jobs"])


class JobResponse(BaseModel):
    ok: bool = True
    job: Job


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, services: ServicesDependency) -> JobResponse:
    return JobResponse(job=services.jobs.get(job_id))
