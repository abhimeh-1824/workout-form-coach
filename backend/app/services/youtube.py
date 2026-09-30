import asyncio
from contextlib import contextmanager
import ipaddress
import logging
from pathlib import Path
import re
import socket
from typing import Any, Dict, Optional
import urllib.error
from urllib.parse import parse_qs, urlparse
import uuid

from starlette.concurrency import run_in_threadpool
import yt_dlp
from yt_dlp.networking._urllib import RedirectHandler

from app.core.config import settings
from app.services.storage import (
    cleanup_path,
    commit_temp_video,
    create_temp_video_path,
)
from app.services.video import VideoValidationError, validate_video_file

logger = logging.getLogger("workout_form_coach.youtube")

# Allowed YouTube entry domains
YOUTUBE_DOMAINS = {
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
}

# Allowed Google/YouTube CDN redirect domains during stream retrieval
ALLOWED_REDIRECT_DOMAINS = {
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "googlevideo.com",
    "ytimg.com",
}


class SSRFProtectionError(Exception):
    """Exception raised when a URL or resolved IP triggers SSRF protection."""
    pass


class YouTubeValidationError(Exception):
    """Exception raised for YouTube URL, metadata, download, or duration errors."""
    pass


def is_private_or_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is private, loopback, link-local, multicast, or cloud metadata."""
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    # Explicit check for AWS/GCP/Azure link-local metadata address
    if ip == ipaddress.ip_address("169.254.169.254"):
        return True

    return False


def validate_ssrf_safe_host(hostname: str) -> None:
    """Resolve hostname and ensure none of its IP addresses fall in restricted ranges."""
    if not hostname:
        raise SSRFProtectionError("Host name cannot be empty.")

    lower_host = hostname.lower()

    # Reject obvious internal or loopback hostnames
    if lower_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise SSRFProtectionError(f"Prohibited hostname: {hostname}")

    if any(lower_host.endswith(suffix) for suffix in (".local", ".internal", ".lan", ".home", ".corp")):
        raise SSRFProtectionError(f"Prohibited internal domain: {hostname}")

    # If the hostname is already an IP literal
    try:
        ip = ipaddress.ip_address(lower_host)
        if is_private_or_restricted_ip(ip):
            raise SSRFProtectionError(f"Prohibited IP address target: {hostname}")
        return
    except ValueError:
        pass

    # Resolve via DNS to inspect all resolved addresses
    try:
        addr_info = socket.getaddrinfo(lower_host, None)
    except socket.gaierror as exc:
        raise SSRFProtectionError(f"DNS resolution failed for {hostname}: {exc}")

    if not addr_info:
        raise SSRFProtectionError(f"No IP addresses resolved for {hostname}")

    for family, _, _, _, sockaddr in addr_info:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if is_private_or_restricted_ip(ip):
                raise SSRFProtectionError(
                    f"Host '{hostname}' resolved to prohibited address {ip_str}"
                )
        except ValueError:
            raise SSRFProtectionError(f"Unparseable IP resolved: {ip_str}")


def is_allowed_domain_pattern(hostname: str, allowed_roots: set[str]) -> bool:
    """Check if hostname matches or is a subdomain of allowed root domains."""
    hostname = hostname.lower()
    for root in allowed_roots:
        if hostname == root or hostname.endswith("." + root):
            return True
    return False


def validate_ssrf_safe_url(url: str, allow_cdn: bool = False) -> None:
    """Validate a URL against SSRF and ensure its destination belongs to allowed domains."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFProtectionError(f"Prohibited URL scheme: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFProtectionError("URL is missing a valid hostname.")

    allowed_roots = ALLOWED_REDIRECT_DOMAINS if allow_cdn else YOUTUBE_DOMAINS
    if not is_allowed_domain_pattern(hostname, allowed_roots):
        raise SSRFProtectionError(f"Domain '{hostname}' is not in the allowed destination list.")

    validate_ssrf_safe_host(hostname)


def validate_youtube_url(url: str) -> str:
    """Validate YouTube URL syntax, domain, and 11-char video ID, returning a canonical URL."""
    if not url or not isinstance(url, str):
        raise YouTubeValidationError("YouTube URL must be a non-empty string.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise YouTubeValidationError("YouTube URL must use http or https scheme.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in YOUTUBE_DOMAINS:
        raise YouTubeValidationError(
            f"Invalid video host '{hostname}'. Only YouTube URLs are accepted."
        )

    video_id: Optional[str] = None
    if hostname == "youtu.be":
        match = re.match(r"^/([a-zA-Z0-9_-]{11})$", parsed.path)
        if match:
            video_id = match.group(1)
    else:
        if parsed.path == "/watch":
            qs = parse_qs(parsed.query)
            v_param = qs.get("v")
            if v_param and re.match(r"^[a-zA-Z0-9_-]{11}$", v_param[0]):
                video_id = v_param[0]
        elif parsed.path.startswith("/shorts/"):
            match = re.match(r"^/shorts/([a-zA-Z0-9_-]{11})$", parsed.path)
            if match:
                video_id = match.group(1)
        elif parsed.path.startswith("/embed/"):
            match = re.match(r"^/embed/([a-zA-Z0-9_-]{11})$", parsed.path)
            if match:
                video_id = match.group(1)

    if not video_id:
        raise YouTubeValidationError(
            "Could not extract a valid 11-character YouTube video ID from the provided URL."
        )

    return f"https://www.youtube.com/watch?v={video_id}"


@contextmanager
def safe_redirect_interceptor():
    """Context manager that hooks into yt-dlp redirect handling to block SSRF on redirects."""
    orig_redirect_request = RedirectHandler.redirect_request

    def safe_redirect_request(self, req, fp, code, msg, headers, newurl):
        try:
            validate_ssrf_safe_url(newurl, allow_cdn=True)
        except SSRFProtectionError as exc:
            logger.warning("SSRF redirect blocked to %s: %s", newurl, exc)
            raise urllib.error.HTTPError(
                req.full_url, 400, f"SSRF redirect blocked: {exc}", headers, fp
            )
        return orig_redirect_request(self, req, fp, code, msg, headers, newurl)

    RedirectHandler.redirect_request = safe_redirect_request
    try:
        yield
    finally:
        RedirectHandler.redirect_request = orig_redirect_request


def _fetch_metadata_sync(canonical_url: str) -> Dict[str, Any]:
    """Retrieve video metadata without downloading video stream."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 10,
    }
    with safe_redirect_interceptor():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                return ydl.extract_info(canonical_url, download=False)
            except yt_dlp.utils.DownloadError as exc:
                err_msg = str(exc)
                logger.warning("yt-dlp metadata extraction failed: %s", err_msg)
                if "Private video" in err_msg or "This video is private" in err_msg:
                    raise YouTubeValidationError("The requested YouTube video is private.")
                if "Video unavailable" in err_msg or "not available" in err_msg:
                    raise YouTubeValidationError("The requested YouTube video is unavailable.")
                if any(x in err_msg.lower() for x in ("sign in", "bot", "blocked")):
                    raise YouTubeValidationError(
                        "Server-side YouTube retrieval is restricted for this video. Please upload the video file directly."
                    )
                raise YouTubeValidationError(
                    "Unable to retrieve YouTube video metadata. Please use the direct upload option."
                )


def _download_video_sync(canonical_url: str, temp_file_path: Path) -> Path:
    """Download video to target temporary path with file size enforcement."""
    outtmpl = str(temp_file_path)
    # yt-dlp may append extension if not present, so we use outtmpl as prefix
    max_bytes = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024

    def progress_hook(d: Dict[str, Any]) -> None:
        if d.get("status") == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            if downloaded > max_bytes:
                raise YouTubeValidationError(
                    f"Download exceeded maximum allowed file size of {settings.MAX_VIDEO_SIZE_MB}MB"
                )

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
        "max_filesize": max_bytes,
        "progress_hooks": [progress_hook],
    }

    with safe_redirect_interceptor():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([canonical_url])
            except yt_dlp.utils.DownloadError as exc:
                err_msg = str(exc)
                logger.warning("yt-dlp download failed: %s", err_msg)
                if "max_filesize" in err_msg or "exceeded" in err_msg:
                    raise YouTubeValidationError(
                        f"Download exceeded maximum allowed file size of {settings.MAX_VIDEO_SIZE_MB}MB"
                    )
                if any(x in err_msg.lower() for x in ("sign in", "bot", "blocked")):
                    raise YouTubeValidationError(
                        "Server-side YouTube retrieval is restricted for this video. Please upload the video file directly."
                    )
                raise YouTubeValidationError(
                    "Failed to download YouTube video. Please use the direct upload option."
                )

    # yt-dlp might have written to temp_file_path or temp_file_path.mp4
    actual_path = temp_file_path
    if not actual_path.exists():
        candidate = Path(str(temp_file_path) + ".mp4")
        if candidate.exists():
            actual_path = candidate
        else:
            # Check for any file starting with temp_file_path stem
            parent = temp_file_path.parent
            matches = list(parent.glob(temp_file_path.name + "*"))
            if matches:
                actual_path = matches[0]
            else:
                raise YouTubeValidationError("Downloaded video file could not be located.")

    return actual_path


async def ingest_youtube_video(job_id: uuid.UUID | str, source_url: str) -> str:
    """Orchestrate YouTube URL validation, SSRF checks, duration pre-check, download, validation, and storage.

    Returns the stored video path on success.
    """
    logger.info("Starting YouTube ingestion for job %s: %s", job_id, source_url)

    # 1. URL validation & normalization
    canonical_url = validate_youtube_url(source_url)

    # 2. SSRF check on entry URL
    validate_ssrf_safe_url(canonical_url, allow_cdn=False)

    # 3. Retrieve metadata & duration pre-check
    metadata = await run_in_threadpool(_fetch_metadata_sync, canonical_url)
    reported_duration = metadata.get("duration")
    if reported_duration is not None and reported_duration > settings.MAX_VIDEO_DURATION_SECONDS:
        raise YouTubeValidationError(
            f"Video duration ({reported_duration:.1f}s) exceeds the maximum allowed limit of {settings.MAX_VIDEO_DURATION_SECONDS} seconds."
        )

    # 4. Download video with hard timeout
    temp_target = create_temp_video_path(job_id)
    actual_temp_file: Optional[Path] = None

    try:
        actual_temp_file = await asyncio.wait_for(
            run_in_threadpool(_download_video_sync, canonical_url, temp_target),
            timeout=float(settings.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS),
        )

        # 5. Validate actual downloaded video (size, container, and true duration)
        validate_video_file(
            actual_temp_file,
            max_size_mb=settings.MAX_VIDEO_SIZE_MB,
            max_duration_seconds=settings.MAX_VIDEO_DURATION_SECONDS,
        )

        # 6. Commit to permanent storage
        stored_path = commit_temp_video(actual_temp_file, job_id, "original.mp4")
        logger.info("Successfully ingested YouTube video for job %s: %s", job_id, stored_path)
        return stored_path

    except asyncio.TimeoutError:
        logger.error("Download timed out after %ds for job %s", settings.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS, job_id)
        cleanup_path(temp_target)
        if actual_temp_file and actual_temp_file != temp_target:
            cleanup_path(actual_temp_file)
        raise YouTubeValidationError(
            f"YouTube video download timed out after {settings.YOUTUBE_DOWNLOAD_TIMEOUT_SECONDS} seconds."
        )
    except Exception:
        cleanup_path(temp_target)
        if actual_temp_file and actual_temp_file != temp_target:
            cleanup_path(actual_temp_file)
        raise
