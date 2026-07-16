"""Progress models and stage labels for the downloader architecture."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum


class DownloadStage(str, Enum):
    """High-level stages a downloader can report."""

    QUEUED = "queued"
    EXTRACTING = "extract"
    SELECTING = "select"
    RETRYING = "retrying"
    DOWNLOADING_VIDEO = "video"
    DOWNLOADING_AUDIO = "audio"
    DOWNLOADING_MEDIA = "download"
    MERGING = "merge"
    EMBEDDING_METADATA = "metadata"
    EMBEDDING_THUMBNAIL = "thumbnail"
    PROCESSING_SUBTITLES = "subtitle"
    CLEANING = "cleanup"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    # Backwards-compatible aliases for older callers.
    ANALYZING = "extract"
    DOWNLOADING = "download"
    PROCESSING = "cleanup"


DOWNLOAD_STAGES: dict[str, str] = {
    "extract": "🔍 Fetching video information",
    # Shown for everything yt-dlp does before media bytes flow (metadata,
    # JS challenges, subtitle fetches, network retries) — keep it generic.
    "select": "🌐 Contacting YouTube (preparing download)",
    "retrying": "⚠ Retrying",
    "video": "⬇ Downloading video stream",
    "audio": "🎵 Downloading audio stream",
    "download": "⬇ Downloading media",
    "merge": "🔄 Merging video and audio",
    "metadata": "🏷 Embedding metadata",
    "thumbnail": "🖼 Embedding thumbnail",
    "subtitle": "💬 Processing subtitles",
    "cleanup": "🧹 Cleaning temporary files",
    "completed": "✅ Download Complete",
    "cancelled": "Download cancelled",
    "failed": "Download failed",
    "queued": "Job queued",
}


def stage_label(stage: DownloadStage | str) -> str:
    """Return the user-facing label for a download stage."""
    key = stage.value if isinstance(stage, DownloadStage) else str(stage)
    return DOWNLOAD_STAGES.get(key, key.replace("_", " ").title())


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """A point-in-time progress snapshot for a download job."""

    job_id: str
    stage: DownloadStage
    percent: float = 0.0
    speed: str = ""
    eta: str = ""
    bytes_downloaded: int = 0
    total_bytes: int | None = None
    message: str = ""
    error: str = ""


ProgressCallback = Callable[[DownloadProgress], None]
