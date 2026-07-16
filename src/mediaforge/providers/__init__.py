"""Provider interfaces and concrete provider stubs."""

from mediaforge.providers.base import FormatInfo, Provider, SubtitleTrack
from mediaforge.providers.capabilities import (
    AudioFormatOption,
    FormatOptions,
    SubtitleLanguageOption,
    SubtitleOptions,
    ThumbnailOption,
    VideoFormatOption,
)
from mediaforge.providers.metadata import (
    AudioFormatMetadata,
    ProviderMediaType,
    ThumbnailMetadata,
    VideoFormatMetadata,
    YouTubeMetadata,
)
from mediaforge.providers.results import DownloadResult, DownloadResultStatus
from mediaforge.providers.youtube import YouTubeProvider

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
