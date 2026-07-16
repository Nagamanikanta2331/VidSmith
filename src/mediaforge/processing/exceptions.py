"""Processing-specific MediaForge exceptions."""

from __future__ import annotations

from mediaforge.utils.exceptions import MediaForgeError


class ProcessingError(MediaForgeError):
    """Base exception for media processing failures."""


class ProcessingValidationError(ProcessingError):
    """Raised when a processing job is invalid."""


class FFmpegNotFoundError(ProcessingError):
    """Raised when the ffmpeg executable cannot be found."""


class FFmpegProcessingError(ProcessingError):
    """Raised when ffmpeg fails during processing."""

    def __init__(self, operation: str, returncode: int | None = None) -> None:
        message = f"FFmpeg failed while running operation: {operation}"
        if returncode is not None:
            message = f"{message} (exit code {returncode})"
        super().__init__(message)
        self.operation = operation
        self.returncode = returncode
