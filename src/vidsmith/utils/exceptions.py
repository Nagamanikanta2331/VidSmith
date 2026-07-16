class VidSmithError(Exception):
    """Base exception for all VidSmith errors."""


class AnalysisError(VidSmithError):
    """Raised when URL analysis fails."""


class UnsupportedURLError(VidSmithError):
    """Raised when a URL is not a recognised YouTube URL."""


class DownloadError(VidSmithError):
    """Raised when a download operation fails."""


class QueueError(VidSmithError):
    """Raised when queued job state is invalid."""


class JobNotFoundError(VidSmithError):
    """Raised when a requested job cannot be found."""

    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job not found: {job_id}")
        self.job_id = job_id
