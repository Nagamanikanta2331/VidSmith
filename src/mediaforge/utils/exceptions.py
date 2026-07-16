class MediaForgeError(Exception):
    """Base exception for all MediaForge errors."""


class AnalysisError(MediaForgeError):
    """Raised when URL analysis fails."""


class UnsupportedURLError(MediaForgeError):
    """Raised when a URL is not a recognised YouTube URL."""


class DownloadError(MediaForgeError):
    """Raised when a download operation fails."""


class QueueError(MediaForgeError):
    """Raised when queued job state is invalid."""


class JobNotFoundError(MediaForgeError):
    """Raised when a requested job cannot be found."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job not found: {job_id}")
        self.job_id = job_id
