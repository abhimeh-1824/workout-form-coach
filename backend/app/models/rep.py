import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.job import Job


class Rep(Base):
    """Rep model representing individual repetition metrics and form analysis."""

    __tablename__ = "reps"

    __table_args__ = (
        sa.UniqueConstraint("job_id", "rep_number", name="uq_reps_job_id_rep_number"),
        sa.CheckConstraint(
            "form_score IS NULL OR (form_score >= 0 AND form_score <= 100)",
            name="ck_reps_form_score_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rep_number: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
    )
    start_time: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    end_time: Mapped[float] = mapped_column(
        sa.Float,
        nullable=False,
    )
    rom: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    tempo: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    form_score: Mapped[Optional[float]] = mapped_column(
        sa.Float,
        nullable=True,
    )
    issues: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB().with_variant(sa.JSON(), "sqlite"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationship
    job: Mapped["Job"] = relationship(
        "Job",
        back_populates="reps",
    )
