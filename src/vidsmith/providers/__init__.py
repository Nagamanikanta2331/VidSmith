"""Provider interfaces and concrete provider stubs."""

from vidsmith.providers.base import FormatInfo, Provider, SubtitleTrack
from vidsmith.providers.capabilities import (
    AudioFormatOption,
    FormatOptions,
    SubtitleLanguageOption,
    SubtitleOptions,
    ThumbnailOption,
    VideoFormatOption,
)
from vidsmith.providers.metadata import (
    AudioFormatMetadata,
    ProviderMediaType,
    ThumbnailMetadata,
    VideoFormatMetadata,
    YouTubeMetadata,
)
from vidsmith.providers.results import DownloadResult, DownloadResultStatus
from vidsmith.providers.youtube import YouTubeProvider

__all__ = [
    "AudioFormatMetadata",
    "AudioFormatOption",
    "DownloadResult",
    "DownloadResultStatus",
    "FormatInfo",
    "FormatOptions",
    "Provider",
    "ProviderMediaType",
    "SubtitleLanguageOption",
    "SubtitleOptions",
    "SubtitleTrack",
    "ThumbnailMetadata",
    "ThumbnailOption",
    "VideoFormatMetadata",
    "VideoFormatOption",
    "YouTubeMetadata",
    "YouTubeProvider",
]
