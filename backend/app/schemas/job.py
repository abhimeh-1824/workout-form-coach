from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.job import ExerciseType, JobStatus, SourceType


class JobCreate(BaseModel):
    """Request payload for creating a new workout analysis job."""

    exercise: ExerciseType = Field(
        ...,
        description="Target exercise category: squat, pushup, or lunge",
    )
    source_type: SourceType = Field(
        ...,
        description="Video submission source: upload or youtube",
    )
    source_url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Required when source_type is youtube; must be omitted for upload",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "JobCreate":
        """Enforce source_url requirements based on source_type."""
        if self.source_type == SourceType.YOUTUBE:
            if not self.source_url or not self.source_url.strip():
                raise ValueError("source_url is required when source_type is 'youtube'")
        elif self.source_type == SourceType.UPLOAD:
            if self.source_url is not None:
                raise ValueError("source_url must not be provided when source_type is 'upload'")
        return self


class JobResponse(BaseModel):
    """Job status and metadata response schema."""

    job_id: uuid.UUID = Field(..., serialization_alias="job_id")
    status: JobStatus
    exercise: ExerciseType
    source_type: SourceType
    source_url: Optional[str] = None
    progress: int
    attempts: int
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processed_video_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @classmethod
    def from_orm_job(cls, job) -> "JobResponse":
        """Map SQLAlchemy Job model to JobResponse."""
        return cls(
            job_id=job.id,
            status=job.status,
            exercise=job.exercise,
            source_type=job.source_type,
            source_url=job.source_url,
            progress=job.progress,
            attempts=job.attempts,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            processed_video_path=job.processed_video_path,
        )


class JobListResponse(BaseModel):
    """Paginated list of jobs for the current authenticated user."""

    items: List[JobResponse]
    total: int
    limit: int
    offset: int


class JobIngestResponse(BaseModel):
    """Minimal response schema returned upon successful video ingestion."""

    job_id: uuid.UUID
    status: str
