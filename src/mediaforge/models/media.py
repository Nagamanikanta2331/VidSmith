from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class MediaType(Enum):
    VIDEO = auto()
    SHORTS = auto()
    PLAYLIST = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class MediaItem:
    url: str
    title: str = ""
    duration: int = 0  # seconds
    uploader: str = ""
    thumbnail_url: str = ""
    view_count: int = 0


@dataclass(frozen=True)
class AudioStreamInfo:
    """One real audio stream reported by yt-dlp during analysis."""

    format_id: str
    codec: str = ""
    bitrate: float = 0.0  # kbps
    language: str = ""
    sample_rate: int = 0  # Hz
    filesize: int = 0  # bytes


@dataclass(frozen=True)
class AnalysisResult:
    url: str
    media_type: MediaType
    title: str = ""
    uploader: str = ""
    thumbnail_url: str = ""
    duration: int = 0  # seconds; 0 for playlists
    view_count: int = 0
    item_count: int = 0  # > 0 for playlists
    items: list[MediaItem] = field(default_factory=list)
    resolutions: list[str] = field(default_factory=list)
    containers: list[str] = field(default_factory=list)
    video_codecs: list[str] = field(default_factory=list)
    audio_codecs: list[str] = field(default_factory=list)
    subtitle_languages: list[str] = field(default_factory=list)
    automatic_subtitle_languages: list[str] = field(default_factory=list)
    audio_languages: list[str] = field(default_factory=list)
    audio_streams: list[AudioStreamInfo] = field(default_factory=list)
    upload_date: str = ""
    video_id: str = ""
    estimated_file_size: int = 0
    error: str = ""

    @property
    def is_playlist(self) -> bool:
        return self.media_type == MediaType.PLAYLIST

    @property
    def failed(self) -> bool:
        return bool(self.error)
