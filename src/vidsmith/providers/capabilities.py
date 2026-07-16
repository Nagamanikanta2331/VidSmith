"""Provider-neutral media capability models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class VideoFormatOption:
    """A normalized downloadable video format option."""

    format_id: str
    resolution: str
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str = ""
    container: str = ""
    filesize: int | None = None
    is_hdr: bool = False
    bitrate: float | None = None
    dynamic_range: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class AudioFormatOption:
    """A normalized downloadable audio format option."""

    format_id: str
    codec: str
    bitrate: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    filesize: int | None = None
    container: str = ""


@dataclass(frozen=True, slots=True)
class FormatOptions:
    """All downloadable media format options for a URL."""

    video: list[VideoFormatOption] = field(default_factory=list)
    audio: list[AudioFormatOption] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SubtitleLanguageOption:
    """Subtitle formats available for one language."""

    language_code: str
    language_name: str
    formats: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SubtitleOptions:
    """Manual and automatic subtitle options for a URL."""

    manual: list[SubtitleLanguageOption] = field(default_factory=list)
    automatic: list[SubtitleLanguageOption] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ThumbnailOption:
    """A normalized downloadable thumbnail option."""

    resolution: str
    width: int | None = None
    height: int | None = None
    preference: int | None = None
    url: str = ""
