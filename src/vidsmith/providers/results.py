"""Provider-neutral download result models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class DownloadResultStatus(str, Enum):
    """Terminal status for a provider download call."""

    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Strongly typed result returned by provider download methods."""

    job_id: str
    url: str
    status: DownloadResultStatus
    output_dir: Path
    files: list[Path] = field(default_factory=list)
    media_type: str = ""
    format_id: str = ""
    title: str = ""
    message: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    # Subtitle outcome, tracked per language. A failed language (e.g. HTTP 429)
    # is recorded here and never treated as a fatal download error.
    subtitles_downloaded: list[str] = field(default_factory=list)
    subtitles_skipped: dict[str, str] = field(default_factory=dict)
    subtitles_failed: dict[str, str] = field(default_factory=dict)
