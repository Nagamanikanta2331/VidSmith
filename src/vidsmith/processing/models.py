"""Strongly typed models for media post-processing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ProcessingOperation(str, Enum):
    """Supported post-processing operations."""

    EMBED_THUMBNAIL = "embed_thumbnail"
    EMBED_SUBTITLES = "embed_subtitles"
    EMBED_METADATA = "embed_metadata"
    MERGE_STREAMS = "merge_streams"
    CONVERT_CONTAINER = "convert_container"
    EXTRACT_AUDIO = "extract_audio"


class ProcessingStatus(str, Enum):
    """Terminal processing status."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SubtitleDisposition(str, Enum):
    """How embedded subtitle tracks should be exposed."""

    DEFAULT = "default"
    FORCED = "forced"
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class SubtitleInput:
    """A subtitle file and its container metadata."""

    path: Path
    language: str = "und"
    title: str = ""
    disposition: SubtitleDisposition = SubtitleDisposition.OPTIONAL


@dataclass(frozen=True, slots=True)
class Chapter:
    """A media chapter represented in milliseconds."""

    start_ms: int
    end_ms: int
    title: str = ""


@dataclass(frozen=True, slots=True)
class MediaMetadata:
    """Metadata fields that can be embedded into output media."""

    title: str = ""
    uploader: str = ""
    description: str = ""
    upload_date: str = ""
    chapters: list[Chapter] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProcessingJob:
    """A complete post-processing request."""

    input_path: Path | None
    output_path: Path
    operations: list[ProcessingOperation]
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    video_path: Path | None = None
    audio_path: Path | None = None
    thumbnail_path: Path | None = None
    subtitles: list[SubtitleInput] = field(default_factory=list)
    metadata: MediaMetadata | None = None
    target_container: str = ""
    audio_format: str = ""
    overwrite: bool = False
    copy_streams: bool = True
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Typed result returned by a media processor."""

    job_id: str
    status: ProcessingStatus
    output_path: Path
    operations: list[ProcessingOperation]
    files: list[Path] = field(default_factory=list)
    message: str = ""
