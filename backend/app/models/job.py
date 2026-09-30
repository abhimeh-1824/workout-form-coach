import enum
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.rep import Rep
    from app.models.report import Report
    from app.models.user import User


class JobStatus(str, enum.Enum):
    """Allowed job processing lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExerciseType(str, enum.Enum):
    """Allowed workout exercise categories."""

    SQUAT = "squat"
    PUSHUP = "pushup"
    LUNGE = "lunge"


class SourceType(str, enum.Enum):
    """Allowed video ingestion source types."""

    UPLOAD = "upload"
    YOUTUBE = "youtube"


class Job(Base):
    """Job model representing video analysis requests."""

    __tablename__ = "jobs"

    __table_args__ = (
        # Worker Job-Claiming Index:
        # Background workers poll for jobs ready to be processed using:
        #   SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED
        # The composite index on (status, created_at) allows workers to immediately filter by 'queued' status
        # and fetch the oldest pending jobs in FIFO order without requiring a full table scan or filesort.
        sa.Index("ix_jobs_status_created_at", "status", "created_at"),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_jobs_progress_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[JobStatus] = mapped_column(
        sa.Enum(
            JobStatus,
            name="job_status",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    exercise: Mapped[ExerciseType] = mapped_column(
        sa.Enum(
            ExerciseType,
            name="exercise_type",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        sa.Enum(
            SourceType,
            name="source_type",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        sa.String(2048),
        nullable=True,
    )
    video_path: Mapped[Optional[str]] = mapped_column(
        sa.String(1024),
        nullable=True,
    )
    processed_video_path: Mapped[Optional[str]] = mapped_column(
        sa.String(1024),
        nullable=True,
    )
    progress: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="jobs",
    )
    reps: Mapped[List["Rep"]] = relationship(
        "Rep",
        back_populates="job",
        cascade="all, delete-orphan",
    )
    report: Mapped[Optional["Report"]] = relationship(
        "Report",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
    )