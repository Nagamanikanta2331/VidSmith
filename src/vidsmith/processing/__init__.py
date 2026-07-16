"""Media post-processing public API."""

from vidsmith.processing.exceptions import (
    FFmpegNotFoundError,
    FFmpegProcessingError,
    ProcessingError,
    ProcessingValidationError,
)
from vidsmith.processing.ffmpeg import FFmpegProcessor
from vidsmith.processing.models import (
    Chapter,
    MediaMetadata,
    ProcessingJob,
    ProcessingOperation,
    ProcessingResult,
    ProcessingStatus,
    SubtitleDisposition,
    SubtitleInput,
)
from vidsmith.processing.processor import MediaProcessor

__all__ = [
    "Chapter",
    "FFmpegNotFoundError",
    "FFmpegProcessingError",
    "FFmpegProcessor",
    "MediaMetadata",
    "MediaProcessor",
    "ProcessingError",
    "ProcessingJob",
    "ProcessingOperation",
    "ProcessingResult",
    "ProcessingStatus",
    "ProcessingValidationError",
    "SubtitleDisposition",
    "SubtitleInput",
]
