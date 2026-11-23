from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.enums import JobStatus, JobType
from app.domain.jobs import Job, JobError
from app.persistence.database import Database
from app.persistence.repositories import JobRepository
from app.services.errors import NotFoundError, ServiceError

ProgressCallback = Callable[[str, int, int], None]
JobWorker = Callable[[ProgressCallback], Awaitable[str | None]]


class JobService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, job_type: JobType, *, total_items: int = 0) -> Job:
        job = Job(
            job_id=f"j_{uuid4().hex}",
            job_type=job_type,
            total_items=total_items,
        )
        with self.database.session_factory.begin() as session:
            JobRepository(session).save(job)
        return job

    def get(self, job_id: str) -> Job:
        with self.database.session_factory() as session:
            job = JobRepository(session).get(job_id)
        if job is None:
            raise NotFoundError("Job", job_id)
        return job

    def _save(self, job: Job) -> None:
        job.updated_at = datetime.now(timezone.utc)
        with self.database.session_factory.begin() as session:
            JobRepository(session).save(job)

    async def run(self, job_id: str, worker: JobWorker) -> None:
        job = self.get(job_id)
        job.status = JobStatus.RUNNING
        job.current_step = "starting"
        self._save(job)

        def progress(step: str, processed: int, total: int) -> None:
            current = self.get(job_id)
            current.status = JobStatus.RUNNING
            current.current_step = step
            current.total_items = max(0, total)
            current.processed_items = max(0, min(processed, current.total_items))
            self._save(current)

        try:
            result_ref = await worker(progress)
            job = self.get(job_id)
            job.status = JobStatus.COMPLETED
            job.current_step = "completed"
            job.processed_items = job.total_items
            job.result_ref = result_ref
            self._save(job)
        except ServiceError as exc:
            job = self.get(job_id)
            job.status = JobStatus.FAILED
            job.current_step = "failed"
            job.error = JobError(
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
            )
            self._save(job)
        except Exception:
            job = self.get(job_id)
            job.status = JobStatus.FAILED
            job.current_step = "failed"
            job.error = JobError(
                code="job_failed",
                message="The background operation failed.",
                retryable=False,
            )
            self._save(job)
