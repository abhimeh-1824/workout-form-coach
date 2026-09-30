import logging
from pathlib import Path
from typing import List
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import Rep, Report
from app.db.session import get_db
from app.models.job import Job, JobStatus, SourceType
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobIngestResponse,
    JobListResponse,
    JobResponse,
)
from app.schemas.rep import JobRepsResponse, RepItemResponse
from app.schemas.report import JobReportResponse
from app.services.storage import (
    cleanup_path,
    commit_temp_video,
    create_temp_video_path,
    get_media_root,
)
from app.services.video import VideoValidationError, validate_video_file
from app.services.youtube import (
    SSRFProtectionError,
    YouTubeValidationError,
    ingest_youtube_video,
)

logger = logging.getLogger("workout_form_coach.jobs")

router = APIRouter(tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workout analysis job",
)
def create_job(
    data: JobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Create a new workout form analysis job in queued status for the authenticated user."""
    job = Job(
        user_id=current_user.id,
        status=JobStatus.QUEUED,
        exercise=data.exercise,
        source_type=data.source_type,
        source_url=data.source_url,
        progress=0,
        attempts=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse.from_orm_job(job)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve a specific job by ID",
)
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Retrieve job details.

    Enforces server-side authorization: returns 404 if the job does not exist
    or if it belongs to another user (never revealing job existence).
    """
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse.from_orm_job(job)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List all jobs for current user",
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100, description="Number of jobs to return (1-100)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobListResponse:
    """Return paginated list of jobs owned by the authenticated user, ordered newest first."""
    count_stmt = select(func.count(Job.id)).where(Job.user_id == current_user.id)
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(Job)
        .where(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    jobs = db.execute(stmt).scalars().all()

    items = [JobResponse.from_orm_job(j) for j in jobs]
    return JobListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{job_id}/video",
    response_model=JobIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload workout video file for a queued job",
)
async def upload_job_video(
    job_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobIngestResponse:
    """Validate, store, and queue an uploaded workout video file for an owned job."""
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.source_type != SourceType.UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not configured for upload source",
        )

    if job.video_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video has already been uploaded for this job",
        )

    temp_target = create_temp_video_path(job.id)
    max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
    total_bytes = 0

    try:
        with open(temp_target, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise VideoValidationError(
                        f"File size ({total_bytes / (1024 * 1024):.1f}MB) exceeds maximum limit of {settings.MAX_VIDEO_SIZE_MB}MB"
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            raise VideoValidationError("Uploaded video file is empty.")

        validate_video_file(
            temp_target,
            max_size_mb=settings.MAX_VIDEO_SIZE_MB,
            max_duration_seconds=settings.MAX_VIDEO_DURATION_SECONDS,
        )

        stored_path = commit_temp_video(temp_target, job.id, "original.mp4")
    except VideoValidationError as exc:
        cleanup_path(temp_target)
        logger.warning("Video upload validation failed for job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        cleanup_path(temp_target)
        logger.error(
            "Unexpected error uploading video for job %s: %s",
            job_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during video upload",
        )
    finally:
        await file.close()

    db.expire(job)
    job.video_path = stored_path
    job.status = JobStatus.QUEUED
    job.error_message = None
    job.progress = 0
    db.commit()
    db.refresh(job)

    return JobIngestResponse(
        job_id=job.id,
        status=job.status.value,
    )


@router.post(
    "/{job_id}/youtube",
    response_model=JobIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest YouTube video for a queued job",
)
async def ingest_youtube(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobIngestResponse:
    """Securely download, validate, and store a YouTube video for an owned job."""
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.source_type != SourceType.YOUTUBE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not configured for YouTube source",
        )

    if job.video_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video has already been ingested for this job",
        )

    if not job.source_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is missing YouTube source URL",
        )

    try:
        stored_path = await ingest_youtube_video(job.id, job.source_url)
    except (YouTubeValidationError, SSRFProtectionError, VideoValidationError) as exc:
        logger.warning("YouTube ingestion validation failed for job %s: %s", job_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error(
            "Unexpected error ingesting YouTube video for job %s: %s",
            job_id,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during video ingestion",
        )

    db.expire(job)
    job.video_path = stored_path
    job.status = JobStatus.QUEUED
    job.error_message = None
    job.progress = 0
    db.commit()
    db.refresh(job)

    return JobIngestResponse(
        job_id=job.id,
        status=job.status.value,
    )


@router.get(
    "/{job_id}/reps",
    response_model=JobRepsResponse,
    summary="Retrieve completed repetition analyses for an owned job",
)
def get_job_reps(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobRepsResponse:
    """Retrieve all completed repetitions and form analysis for an owned job.

    Enforces ownership authorization: returns 404 if the job does not exist
    or if it belongs to another user.
    """
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    reps_stmt = (
        select(Rep)
        .where(Rep.job_id == job_id)
        .order_by(Rep.rep_number.asc())
    )
    reps = db.execute(reps_stmt).scalars().all()

    items = [
        RepItemResponse(
            rep_number=r.rep_number,
            start_time=round(r.start_time, 2),
            end_time=round(r.end_time, 2),
            rom=round(r.rom, 1) if r.rom is not None else None,
            tempo=round(r.tempo, 2) if r.tempo is not None else None,
            form_score=round(r.form_score, 1) if r.form_score is not None else None,
            issues=r.issues if r.issues is not None else [],
        )
        for r in reps
    ]

    return JobRepsResponse(
        job_id=job.id,
        total_reps=len(items),
        reps=items,
    )


@router.get(
    "/{job_id}/report",
    response_model=JobReportResponse,
    summary="Retrieve aggregate workout report for an owned job",
)
def get_job_report(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobReportResponse:
    """Retrieve aggregate workout summary report for an owned job.

    Enforces ownership authorization: returns 404 if the job does not exist,
    belongs to another user, or report is not yet available.
    """
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    report_stmt = select(Report).where(Report.job_id == job_id)
    report = db.execute(report_stmt).scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this job",
        )

    return JobReportResponse(
        job_id=job.id,
        total_reps=report.total_reps,
        average_rom=round(report.average_rom, 1) if report.average_rom is not None else None,
        average_tempo=round(report.average_tempo, 2) if report.average_tempo is not None else None,
        average_score=round(report.average_score, 1) if report.average_score is not None else None,
        summary=report.summary,
    )


@router.get(
    "/{job_id}/video",
    summary="Retrieve workout video file (processed or original) for an owned job",
)
def get_job_processed_video(
    job_id: uuid.UUID,
    type: str = Query("processed", pattern="^(processed|original)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Securely stream/download workout video (annotated processed or original feed).

    Enforces ownership authorization and strict path traversal protection.
    """
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Determine requested video path
    target_rel_path: Optional[str] = None
    if type == "original":
        target_rel_path = job.video_path
        if not target_rel_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original video not available for this job",
            )
    else:
        # Defaults to processed; falls back to original video if processing pending
        target_rel_path = job.processed_video_path or job.video_path
        if not target_rel_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not available for this job",
            )

    media_root = get_media_root().resolve()
    clean_rel_path = target_rel_path.replace("\\", "/")
    if clean_rel_path.startswith("media/"):
        clean_rel_path = clean_rel_path[len("media/") :]

    video_path = Path(clean_rel_path)
    if not video_path.is_absolute():
        video_path = (media_root / video_path).resolve()
    else:
        video_path = video_path.resolve()

    # Path traversal protection
    if not video_path.is_relative_to(media_root) or not video_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video file not found on storage",
        )

    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=f"{type}_{job.id}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete an owned workout job and its associated files",
)
def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Permanently delete an owned workout job, cascading to reps, reports, and disk files."""
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Clean up disk assets for original and processed videos
    media_root = get_media_root().resolve()
    job_media_dir = media_root / "jobs" / str(job_id)
    if job_media_dir.exists():
        cleanup_path(job_media_dir)

    processed_media_dir = media_root / "processed" / str(job_id)
    if processed_media_dir.exists():
        cleanup_path(processed_media_dir)

    # Delete Job row (cascades to reps and report in PostgreSQL)
    db.delete(job)
    db.commit()

    return {
        "message": "Workout job deleted successfully",
        "job_id": str(job_id),
    }


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry a failed or completed job",
)
async def retry_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Reset a workout analysis job back to queued status for re-processing.
    
    If video_path is missing but source is YouTube, re-downloads the video.
    """
    stmt = select(Job).where(
        Job.id == job_id,
        Job.user_id == current_user.id,
    )
    job = db.execute(stmt).scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # If video path is missing on disk and source is YouTube, re-ingest
    media_root = get_media_root().resolve()
    has_video = False
    if job.video_path:
        clean_rel = job.video_path.replace("\\", "/")
        if clean_rel.startswith("media/"):
            clean_rel = clean_rel[len("media/") :]
        has_video = (media_root / clean_rel).is_file()

    if not has_video and job.source_type == SourceType.YOUTUBE and job.source_url:
        try:
            stored_path = await ingest_youtube_video(job.id, job.source_url)
            job.video_path = stored_path
        except Exception as exc:
            logger.error("Failed to re-ingest YouTube video on retry: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to download YouTube video: {exc}",
            )

    job.status = JobStatus.QUEUED
    job.progress = 0
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    db.refresh(job)

    return JobResponse.from_orm_job(job)

