from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import JobStatus, JobType


class JobError(BaseModel):
    code: str
    message: str
    retryable: bool = False


class Job(BaseModel):
    job_id: str = Field(min_length=1, max_length=128)
    job_type: JobType
    status: JobStatus = JobStatus.QUEUED
    current_step: str = "queued"
    processed_items: int = Field(default=0, ge=0)
    total_items: int = Field(default=0, ge=0)
    result_ref: str | None = None
    error: JobError | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_progress_and_error(self) -> "Job":
        if self.processed_items > self.total_items:
            raise ValueError("processed_items cannot exceed total_items.")
        if self.status == JobStatus.FAILED and self.error is None:
            raise ValueError("A failed job requires an error.")
        if self.status != JobStatus.FAILED and self.error is not None:
            raise ValueError("Only a failed job may expose an error.")
        return self
