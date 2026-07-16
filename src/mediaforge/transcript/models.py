"""Strongly typed transcript models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class TranscriptFormat(str, Enum):
    """Supported input transcript formats."""

    VTT = "vtt"
    SRT = "srt"
    TTML = "ttml"


class TranscriptOutputFormat(str, Enum):
    """Supported transcript export formats."""

    MARKDOWN = "md"
    TEXT = "txt"
    JSON = "json"
    SRT = "srt"
    VTT = "vtt"


class TimestampMode(str, Enum):
    """How timestamps should appear in exported documents."""

    NONE = "none"
    START = "start"
    START_END = "start_end"


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """A single structured transcript cue."""

    start: float
    end: float
    text: str
    speaker: str = ""


@dataclass(frozen=True, slots=True)
class TranscriptDocument:
    """A parsed and cleaned transcript."""

    segments: list[TranscriptSegment]
    title: str = "Transcript"
    language: str = ""
    source_path: Path | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TranscriptJob:
    """A full transcript conversion request."""

    input_path: Path
    output_path: Path
    output_format: TranscriptOutputFormat
    input_format: TranscriptFormat | None = None
    timestamp_mode: TimestampMode = TimestampMode.START
    title: str = "Transcript"
    language: str = ""


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    """Result returned after a transcript export."""

    output_path: Path
    output_format: TranscriptOutputFormat
    segment_count: int
    title: str

@dataclass(frozen=True, slots=True)
class TranscriptValidationResult:
    """Result of transcript conversion phase."""

    success: bool
    output_format: str
    output_file: Path | None = None
    error_message: str | None = None
