"""Background job worker process.

Continuously polls the PostgreSQL jobs table using row-level locking
(FOR UPDATE SKIP LOCKED) to claim queued jobs and execute video processing.
"""

from datetime import datetime, timezone
import inspect
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.base import Job, JobStatus
from app.db.session import SessionLocal
from app.services.job_queue import claim_next_job, find_stale_processing_jobs
from app.services.storage import cleanup_orphaned_media
from app.services.video_processor import finalize_job_failure, process_job

logger = logging.getLogger("workout_form_coach.worker")


def execute_custom_processor(
    processor: Callable[..., Any],
    job: Job,
    factory: sessionmaker[Session],
) -> None:
    """Execute custom processor accommodating both (job, db) and (job, factory) signatures."""
    sig = inspect.signature(processor)
    params = list(sig.parameters.values())

    if len(params) >= 2 and params[1].name in ("db", "session"):
        with factory() as session:
            processor(job, session)
    elif len(params) >= 2:
        processor(job, factory)
    elif len(params) == 1:
        processor(job)
    else:
        processor(job, factory)


def recover_stale_jobs(factory: sessionmaker[Session]) -> None:
    """Detect jobs stuck in PROCESSING due to previous worker or container crashes."""
    try:
        with factory() as db:
            stale_jobs = find_stale_processing_jobs(db, stale_threshold_seconds=180)
            for job in stale_jobs:
                video_exists = False
                if job.video_path:
                    p = Path(job.video_path)
                    video_exists = p.exists() if p.is_absolute() else (Path(settings.MEDIA_ROOT) / p).exists() or p.exists()

                if not video_exists or job.attempts >= 3:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = (
                        "Processing was interrupted by a server restart or timeout. Please re-upload your workout video."
                    )
                    logger.warning("Marked crashed/unrecoverable job %s as FAILED", job.id)
                else:
                    job.status = JobStatus.QUEUED
                    logger.info("Reset crashed job %s back to QUEUED for retry", job.id)
            db.commit()
    except Exception as exc:
        logger.warning("Stale job recovery encountered error: %s", exc)


def run_worker(
    db_factory: Optional[sessionmaker[Session]] = None,
    poll_interval: Optional[float] = None,
    stop_event: Optional[threading.Event] = None,
    max_iterations: Optional[int] = None,
    processor: Optional[Callable[..., Any]] = None,
) -> None:
    """Run the background worker polling loop.

    Transaction Safety Architecture:
    1. Claim job in a short, atomic transaction (claim_next_job).
    2. Execute video processing completely outside the claim transaction.
    3. Update progress periodically via short transactional bursts.
    4. Finalize status (COMPLETED / FAILED) in a brief transaction.
    5. Handle processing exceptions gracefully and continue processing subsequent jobs.

    Args:
        db_factory: SQLAlchemy sessionmaker factory. Defaults to SessionLocal.
        poll_interval: Seconds to wait between polling when the queue is empty.
        stop_event: Threading event to signal graceful termination.
        max_iterations: Optional limit on loop iterations (useful for tests).
        processor: Optional processing callable. Defaults to app.services.video_processor.process_job.
    """
    factory = db_factory or SessionLocal
    interval = poll_interval if poll_interval is not None else settings.WORKER_POLL_INTERVAL_SECONDS
    event = stop_event or threading.Event()

    logger.info(
        "Worker started. Polling interval: %s seconds. Processing FPS: %d.",
        interval,
        settings.PROCESSING_FPS,
    )

    # Initial automated cleanup of orphaned media folders and stale jobs
    try:
        with factory() as db:
            cleanup_orphaned_media(db)
        recover_stale_jobs(factory)
    except Exception as cleanup_err:
        logger.warning("Initial storage cleanup encountered error: %s", cleanup_err)

    iteration_count = 0
    while not event.is_set():
        if max_iterations is not None and iteration_count >= max_iterations:
            logger.info("Worker reached max iterations (%d). Stopping loop.", max_iterations)
            break
        iteration_count += 1

        # Periodic check for stale crashed jobs every 30 iterations (~1 min)
        if iteration_count % 30 == 0:
            recover_stale_jobs(factory)

        # Periodic storage maintenance every 300 iterations (~10 mins)
        if iteration_count % 300 == 0:
            try:
                with factory() as db:
                    cleanup_orphaned_media(db)
            except Exception as cleanup_err:
                logger.warning("Periodic storage cleanup encountered error: %s", cleanup_err)

        # 1. Claim job in a short, isolated transaction
        job = None
        try:
            with factory() as db:
                job = claim_next_job(db)
        except Exception as queue_exc:
            logger.exception("Unexpected error claiming next job from queue: %s", queue_exc)
            event.wait(timeout=interval)
            continue

        if not job:
            logger.debug("No queued jobs available. Waiting %s seconds...", interval)
            event.wait(timeout=interval)
            continue

        logger.info(
            "Worker claimed job %s (attempt=%d, exercise=%s). Dispatching to video processor.",
            job.id,
            job.attempts,
            job.exercise.value,
        )

        # 2. Process video outside long-lived database transactions
        try:
            if processor is not None:
                execute_custom_processor(processor, job, factory)
            else:
                process_job(job, db_factory=factory)
        except Exception as exc:
            logger.exception(
                "Worker encountered error while processing job %s (attempt=%d): %s",
                job.id,
                job.attempts,
                exc,
            )
            # Ensure job is marked as FAILED in an isolated transaction
            finalize_job_failure(factory, job.id, f"Processing failed: {exc}")

    logger.info("Worker loop terminated gracefully.")


def main() -> None:
    """CLI entrypoint for running the worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    stop_event = threading.Event()

    def handle_signal(sig, frame):
        logger.info("Received shutdown signal (%d). Initiating graceful worker shutdown...", sig)
        stop_event.set()

    # Register OS signals for graceful shutdown (SIGINT = Ctrl+C, SIGTERM = Docker stop)
    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    run_worker(stop_event=stop_event)


if __name__ == "__main__":
    main()
