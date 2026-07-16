"""Downloader architecture primitives."""

from vidsmith.downloader.engine import DownloadEngine
from vidsmith.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    JobStatus,
    MetadataMode,
    PlaylistOptions,
    SubtitleMode,
    ThumbnailMode,
)
from vidsmith.downloader.manager import DownloadManager
from vidsmith.downloader.progress import DownloadProgress, DownloadStage, ProgressCallback
from vidsmith.downloader.queue import DownloadQueue

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
