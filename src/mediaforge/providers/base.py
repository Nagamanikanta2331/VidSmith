"""Abstract provider contract for media download backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from mediaforge.downloader.job import DownloadJob
from mediaforge.downloader.progress import ProgressCallback
from mediaforge.providers.capabilities import FormatOptions, SubtitleOptions, ThumbnailOption
from mediaforge.providers.metadata import YouTubeMetadata
from mediaforge.providers.results import DownloadResult


@dataclass(frozen=True, slots=True)
class FormatInfo:
    """Provider-neutral description of an available media format."""

    format_id: str
    extension: str
    resolution: str = ""
    audio_codec: str = ""
    video_codec: str = ""
    filesize: int | None = None
    bitrate: int | None = None


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    """Provider-neutral description of an available subtitle track."""

    language: str
    name: str = ""
    extension: str = "vtt"
    is_automatic: bool = False


class Provider(ABC):
    """Interface every media provider must implement."""

    @abstractmethod
    def analyze(self, url: str) -> YouTubeMetadata:
        """Return provider metadata for a URL."""

    @abstractmethod
    def get_formats(self, url: str) -> FormatOptions:
        """Return formats available for a URL."""

    @abstractmethod
    def get_subtitles(self, url: str) -> SubtitleOptions:
        """Return subtitle tracks available for a URL."""

    @abstractmethod
    def get_thumbnail_options(self, url: str) -> list[ThumbnailOption]:
        """Return thumbnail options available for a URL."""

    @abstractmethod
    def get_thumbnail(self, url: str) -> str | None:
        """Return a thumbnail URL or provider identifier."""

    @abstractmethod
    def download(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download the primary media artifact for a job."""

    @abstractmethod
    def download_audio(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download or extract audio for a job."""

    @abstractmethod
    def download_subtitles(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download subtitle files for a job."""

    @abstractmethod
    def download_thumbnail(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download thumbnail assets for a job."""

    @abstractmethod
    def download_transcript(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download or generate a transcript artifact for a job."""
