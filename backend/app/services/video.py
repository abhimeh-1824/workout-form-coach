import logging
import os
from pathlib import Path
import shutil
import subprocess
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("workout_form_coach.video")


class VideoValidationError(Exception):
    """Exception raised when a video fails size, container, or duration validation."""
    pass


def probe_video_duration(file_path: Path) -> float:
    """Probe video duration in seconds using ffprobe or fallback inspection."""
    ffprobe_cmd = shutil.which("ffprobe")
    if not ffprobe_cmd:
        logger.warning("ffprobe not found on PATH; falling back to basic inspection")
        # If ffprobe is not installed, verify file is non-empty
        if file_path.stat().st_size < 100:
            raise VideoValidationError("Video file is corrupt or empty.")
        return 0.0

    try:
        cmd = [
            ffprobe_cmd,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.error("ffprobe error inspecting %s: %s", file_path, result.stderr.strip())
            raise VideoValidationError("Downloaded file is not a valid or readable video.")

        output = result.stdout.strip()
        if not output:
            raise VideoValidationError("Could not determine video duration.")

        duration = float(output)
        return duration
    except subprocess.TimeoutExpired:
        raise VideoValidationError("Timeout while analyzing video format.")
    except ValueError:
        raise VideoValidationError("Invalid duration returned from video metadata.")


def validate_video_file(
    file_path: Path,
    max_size_mb: Optional[int] = None,
    max_duration_seconds: Optional[int] = None,
) -> float:
    """Validate that the file exists, satisfies size limits, is a valid video, and meets duration constraints."""
    if max_size_mb is None:
        max_size_mb = settings.MAX_VIDEO_SIZE_MB
    if max_duration_seconds is None:
        max_duration_seconds = settings.MAX_VIDEO_DURATION_SECONDS

    if not file_path.exists():
        raise VideoValidationError("Video file does not exist.")

    file_size = file_path.stat().st_size
    if file_size == 0:
        raise VideoValidationError("Video file is empty.")

    max_bytes = max_size_mb * 1024 * 1024
    if file_size > max_bytes:
        raise VideoValidationError(
            f"File size ({file_size / (1024 * 1024):.1f}MB) exceeds maximum limit of {max_size_mb}MB"
        )

    # Validate header signature
    with open(file_path, "rb") as f:
        header = f.read(32)

    is_mp4 = len(header) >= 8 and (b"ftyp" in header[:12] or b"moov" in header[:12])
    is_webm = header.startswith(b"\x1a\x45\xdf\xa3")
    is_avi = header.startswith(b"RIFF") and b"AVI " in header[8:12]

    if not (is_mp4 or is_webm or is_avi):
        raise VideoValidationError("File does not have a recognized video header.")

    # Probe duration
    duration = probe_video_duration(file_path)
    if duration > max_duration_seconds:
        raise VideoValidationError(
            f"Video duration ({duration:.1f}s) exceeds maximum allowed {max_duration_seconds}s"
        )

    logger.info("Video validated successfully: %s (%.1fs, %d bytes)", file_path.name, duration, file_size)
    return duration
