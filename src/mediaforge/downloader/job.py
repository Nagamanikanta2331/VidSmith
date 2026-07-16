"""Download job models for the downloader architecture."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class DownloadMediaType(str, Enum):
    """The kind of artifact a download job should produce."""

    VIDEO = "video"
    AUDIO = "audio"
    TRANSCRIPT = "transcript"
    PLAYLIST = "playlist"


class JobStatus(str, Enum):
    """Lifecycle states for a queued download job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubtitleMode(str, Enum):
    """Subtitle source preference for a job."""

    NONE = "none"
    AUTO = "auto"
    MANUAL = "manual"
    BOTH = "both"


class ThumbnailMode(str, Enum):
    """How thumbnail data should be handled."""

    NONE = "none"
    EMBED = "embed"
    SAVE = "save"
    BOTH = "both"


class MetadataMode(str, Enum):
    """How media metadata should be handled."""

    NONE = "none"
    EMBED = "embed"
    SAVE = "save"


@dataclass(slots=True)
class PlaylistOptions:
    """Options that apply when a job targets a playlist."""

    selection: str = "all"
    item_range: str = ""
    concurrency: int = 1
    reverse_order: bool = False
    include_unavailable: bool = False
    output_template: str = "%(playlist_index)s - %(title)s.%(ext)s"


@dataclass(slots=True)
class DownloadJob:
    """A complete, UI-independent specification for a future download."""

    url: str
    media_type: DownloadMediaType
    output_dir: Path
    quality: str = "best"
    # Exact yt-dlp format selector; when set it overrides quality/container
    # based selection (used by Best Download's fixed VP9 preference chain).
    format_selector: str = ""
    subtitle_languages: list[str] = field(default_factory=list)
    # Base language codes the user (or a preset) asked for, including ones
    # that turned out to be unavailable — the summary reports each of these.
    subtitle_requested_languages: list[str] = field(default_factory=list)
    # Resolved codes that will come from auto-generated captions, so the
    # summary can label them "(Auto)".
    subtitle_auto_languages: list[str] = field(default_factory=list)
    subtitle_mode: SubtitleMode = SubtitleMode.NONE
    thumbnail_mode: ThumbnailMode = ThumbnailMode.NONE
    metadata_mode: MetadataMode = MetadataMode.EMBED
    audio_format: str = "mp3"
    audio_quality: str = "192k"
    audio_stream_id: str = ""  # yt-dlp format_id of a specific source audio stream
    video_format: str = "mp4"
    audio_language: str = ""
    transcript_format: str = "txt"
    include_timestamps: bool = False
    overwrite: bool = False
    output_template: str = "%(title)s.%(ext)s"
    playlist_options: PlaylistOptions | None = None
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    error_message: str = ""

    @property
    def is_playlist(self) -> bool:
        return self.media_type == DownloadMediaType.PLAYLIST

    @property
    def is_audio(self) -> bool:
        return self.media_type == DownloadMediaType.AUDIO

    @property
    def is_transcript(self) -> bool:
        return self.media_type == DownloadMediaType.TRANSCRIPT

    def mark_running(self) -> None:
        self.status = JobStatus.RUNNING
        self.updated_at = datetime.now()

    def mark_completed(self) -> None:
        self.status = JobStatus.COMPLETED
        self.updated_at = datetime.now()

    def mark_failed(self, reason: str) -> None:
        self.status = JobStatus.FAILED
        self.error_message = reason
        self.updated_at = datetime.now()

    def mark_cancelled(self) -> None:
        self.status = JobStatus.CANCELLED
        self.updated_at = datetime.now()

    def reset_for_retry(self) -> None:
        self.status = JobStatus.PENDING
        self.error_message = ""
        self.updated_at = datetime.now()
