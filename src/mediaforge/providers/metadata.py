"""Provider-neutral metadata models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProviderMediaType(str, Enum):
    """Media kinds exposed by providers."""

    VIDEO = "video"
    SHORTS = "shorts"
    PLAYLIST = "playlist"


@dataclass(frozen=True, slots=True)
class ThumbnailMetadata:
    """A normalized thumbnail reference."""

    url: str
    width: int | None = None
    height: int | None = None
    resolution: str = ""
    thumbnail_id: str = ""


@dataclass(frozen=True, slots=True)
class VideoFormatMetadata:
    """A normalized playable video format."""

    format_id: str
    extension: str
    container: str
    resolution: str
    fps: float | None = None
    video_codec: str = ""
    filesize: int | None = None
    dynamic_range: str = ""


@dataclass(frozen=True, slots=True)
class AudioFormatMetadata:
    """A normalized playable audio format."""

    format_id: str
    extension: str
    container: str
    audio_codec: str
    bitrate: float | None = None
    filesize: int | None = None


@dataclass(frozen=True, slots=True)
class YouTubeMetadata:
    """Normalized YouTube metadata used by the rest of MediaForge."""

    url: str
    title: str = ""
    uploader: str = ""
    channel_id: str = ""
    video_id: str = ""
    duration: int | None = None
    description: str = ""
    upload_date: str = ""
    view_count: int | None = None
    like_count: int | None = None
    thumbnail_url: str = ""
    thumbnails: list[ThumbnailMetadata] = field(default_factory=list)
    media_type: ProviderMediaType = ProviderMediaType.VIDEO
    playlist_title: str = ""
    playlist_count: int | None = None
    subtitle_languages: list[str] = field(default_factory=list)
    automatic_subtitle_languages: list[str] = field(default_factory=list)
    video_formats: list[VideoFormatMetadata] = field(default_factory=list)
    audio_formats: list[AudioFormatMetadata] = field(default_factory=list)
    containers: list[str] = field(default_factory=list)
    resolutions: list[str] = field(default_factory=list)
    fps_values: list[float] = field(default_factory=list)
    hdr_formats: list[str] = field(default_factory=list)
