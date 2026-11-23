from functools import partial

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from app.api.dependencies import ServicesDependency
from app.domain.enums import JobType
from app.domain.jobs import Job
from app.domain.recommendations import RecommendationRun, StartRecommendationRequest

router = APIRouter(tags=["recommendations"])


class RecommendationStartResponse(BaseModel):
    ok: bool = True
    run_id: str
    job: Job


class RecommendationResponse(BaseModel):
    ok: bool = True
    recommendation: RecommendationRun


@router.post(
    "/recommendations",
    response_model=RecommendationStartResponse,
    status_code=202,
)
async def start_recommendation(
    request: StartRecommendationRequest,
    background_tasks: BackgroundTasks,
    services: ServicesDependency,
) -> RecommendationStartResponse:
    run = services.recommendation.create_run(request)
    job = services.jobs.create(JobType.RECOMMENDATION, total_items=2)
    worker = partial(services.recommendation.execute, run.run_id, request)
    background_tasks.add_task(services.jobs.run, job.job_id, worker)
    return RecommendationStartResponse(run_id=run.run_id, job=job)


@router.get(
    "/recommendations/{run_id}", response_model=RecommendationResponse
)
async def get_recommendation(
    run_id: str, services: ServicesDependency
) -> RecommendationResponse:
    return RecommendationResponse(
        recommendation=services.recommendation.get(run_id)
    )
