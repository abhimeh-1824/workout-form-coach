from datetime import datetime, timedelta, timezone
import logging
from typing import List, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.base import Job, JobStatus

logger = logging.getLogger("workout_form_coach.job_queue")


def claim_next_job(db: Session) -> Optional[Job]:
    """Atomically select and claim the oldest queued job using PostgreSQL row-level locking.

    Uses `FOR UPDATE SKIP LOCKED` to guarantee that concurrent workers never claim
    the same job simultaneously. Transitions status to 'processing', sets started_at,
    and increments the attempts counter within a single atomic transaction.
    """
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.QUEUED,
            Job.video_path.isnot(None),
        )
        .order_by(Job.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )

    job = db.execute(stmt).scalars().first()
    if not job:
        return None

    # Transition atomically within the lock to processing
    now = datetime.now(timezone.utc)
    job.status = JobStatus.PROCESSING
    job.started_at = now
    job.attempts += 1

    db.commit()
    db.refresh(job)

    logger.info(
        "Claimed job %s (exercise=%s, attempt=%d) for processing",
        job.id,
        job.exercise.value,
        job.attempts,
    )
    return job


def find_stale_processing_jobs(
    db: Session,
    stale_threshold_seconds: int = 600,
) -> List[Job]:
    """Locate processing jobs whose started_at timestamp exceeds the stale threshold.

    Prepared for future recovery mechanisms to detect workers that crashed while processing.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=stale_threshold_seconds)
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.PROCESSING,
            Job.started_at <= cutoff_time,
        )
        .order_by(Job.started_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


def reset_stale_job(db: Session, job_id: uuid.UUID) -> Optional[Job]:
    """Reset a confirmed crashed/stale processing job back to queued for retry."""
    stmt = (
        select(Job)
        .where(Job.id == job_id, Job.status == JobStatus.PROCESSING)
        .with_for_update(skip_locked=True)
    )
    job = db.execute(stmt).scalars().first()
    if not job:
        return None

    job.status = JobStatus.QUEUED
    db.commit()
    db.refresh(job)
    logger.warning("Reset stale processing job %s back to queued", job.id)
    return job
