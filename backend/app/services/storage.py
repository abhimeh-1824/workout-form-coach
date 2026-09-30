import logging
import os
from pathlib import Path
import shutil
from typing import Optional
import uuid

from app.core.config import settings

logger = logging.getLogger("workout_form_coach.storage")


def get_media_root() -> Path:
    """Return the base media directory as a resolved Path object."""
    root = Path(settings.MEDIA_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_job_dir(job_id: uuid.UUID | str) -> Path:
    """Return the dedicated storage directory for a specific job."""
    job_dir = get_media_root() / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_job_video_path(job_id: uuid.UUID | str, filename: str = "original.mp4") -> Path:
    """Return the final storage path for a job's primary video file."""
    return get_job_dir(job_id) / filename


def get_job_processed_video_path(job_id: uuid.UUID | str, filename: str = "processed.mp4") -> Path:
    """Return the storage path for a job's processed output video."""
    processed_dir = get_media_root() / "processed" / str(job_id)
    processed_dir.mkdir(parents=True, exist_ok=True)
    return processed_dir / filename


def get_job_processed_relative_path(job_id: uuid.UUID | str, filename: str = "processed.mp4") -> str:
    """Return the relative POSIX path for database storage."""
    return f"processed/{job_id}/{filename}"


def create_temp_video_path(job_id: uuid.UUID | str, suffix: str = ".mp4") -> Path:
    """Create a temporary path for downloading and validating videos before commitment."""
    temp_dir = get_media_root() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    unique_id = uuid.uuid4().hex
    return temp_dir / f"job_{job_id}_{unique_id}{suffix}"


def commit_temp_video(
    temp_path: Path,
    job_id: uuid.UUID | str,
    filename: str = "original.mp4",
) -> str:
    """Atomically move a validated temporary video into permanent job storage.

    Returns the normalized relative POSIX path for database storage.
    """
    final_path = get_job_video_path(job_id, filename)
    shutil.move(str(temp_path), str(final_path))
    logger.info("Committed video for job %s to %s", job_id, final_path)
    return final_path.as_posix()


def cleanup_path(path: Optional[Path]) -> None:
    """Safely remove a file or directory if it exists."""
    if path and path.exists():
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            logger.warning("Failed to clean up path %s: %s", path, exc)


def cleanup_orphaned_media(db, max_temp_age_hours: int = 1) -> dict[str, int]:
    """Scan storage folders (media/jobs, media/processed, media/temp) and automatically remove orphaned or stale data.

    Any job directory on disk that does not correspond to an existing job in the database is purged.
    """
    from datetime import datetime
    from sqlalchemy import select
    from app.models.job import Job

    stats = {"jobs_removed": 0, "processed_removed": 0, "temp_removed": 0}
    try:
        active_ids = {str(row) for row in db.execute(select(Job.id)).scalars().all()}
    except Exception as exc:
        logger.warning("Could not query active job IDs for media cleanup: %s", exc)
        return stats

    media_root = get_media_root().resolve()

    # Clean media/jobs
    jobs_dir = media_root / "jobs"
    if jobs_dir.exists() and jobs_dir.is_dir():
        for item in jobs_dir.iterdir():
            if item.is_dir() and item.name not in active_ids:
                cleanup_path(item)
                stats["jobs_removed"] += 1

    # Clean media/processed
    processed_dir = media_root / "processed"
    if processed_dir.exists() and processed_dir.is_dir():
        for item in processed_dir.iterdir():
            if item.is_dir() and item.name not in active_ids:
                cleanup_path(item)
                stats["processed_removed"] += 1

    # Clean stale media/temp
    temp_dir = media_root / "temp"
    if temp_dir.exists() and temp_dir.is_dir():
        cutoff = datetime.now().timestamp() - (max_temp_age_hours * 3600)
        for item in temp_dir.iterdir():
            if item.is_file() and item.stat().st_mtime < cutoff:
                cleanup_path(item)
                stats["temp_removed"] += 1

    if any(stats.values()):
        logger.info(
            "Automated storage cleanup completed: %d raw jobs, %d processed, %d temp files removed.",
            stats["jobs_removed"],
            stats["processed_removed"],
            stats["temp_removed"],
        )

    return stats

