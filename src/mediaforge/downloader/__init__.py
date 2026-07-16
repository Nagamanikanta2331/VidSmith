"""Downloader architecture primitives."""

from mediaforge.downloader.engine import DownloadEngine
from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    JobStatus,
    MetadataMode,
    PlaylistOptions,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.downloader.manager import DownloadManager
from mediaforge.downloader.progress import DownloadProgress, DownloadStage, ProgressCallback
from mediaforge.downloader.queue import DownloadQueue

__all__ = [
    "DownloadEngine",
    "DownloadJob",
    "DownloadManager",
    "DownloadMediaType",
    "DownloadProgress",
    "DownloadQueue",
    "DownloadStage",
    "JobStatus",
    "MetadataMode",
    "PlaylistOptions",
    "ProgressCallback",
    "SubtitleMode",
    "ThumbnailMode",
]
