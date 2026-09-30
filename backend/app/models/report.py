import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class Report(Base):
    """Report model representing aggregated analysis summary for a job."""

    __tablename__ = "reports"

    __table_args__ = (
        sa.UniqueConstraint("job_id", name="uq_reports_job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_reps: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        nullable=False,
    )
    average_score: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    average_rom: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    average_tempo: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        sa.Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationship (1-to-1 with Job)
    job: Mapped["Job"] = relationship(
        "Job",
        back_populates="report",
    )
