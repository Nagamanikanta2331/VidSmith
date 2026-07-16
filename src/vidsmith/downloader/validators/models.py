from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class ValidationErrorCode:
    FILE_MISSING = "FILE_MISSING"
    FILE_EMPTY = "FILE_EMPTY"
    SUBTITLE_MISSING = "SUBTITLE_MISSING"
    THUMBNAIL_NOT_EMBEDDED = "THUMBNAIL_NOT_EMBEDDED"
    METADATA_MISSING = "METADATA_MISSING"
    TRANSCRIPT_FAILED = "TRANSCRIPT_FAILED"
    SUBTITLE_FAILED = "SUBTITLE_FAILED"
    AUDIO_VALIDATION_FAILED = "AUDIO_VALIDATION_FAILED"


@dataclass
class SubtitleValidationResult:
    downloaded_languages: list[str] = field(default_factory=list)
    embedded_languages: list[str] = field(default_factory=list)
    sidecar_languages: list[str] = field(default_factory=list)
    failed_languages: dict[str, str] = field(default_factory=dict)
    success: bool = True


@dataclass
class AudioValidationResult:
    artwork_status: str = "Unsupported"
    metadata_present: bool = False
    title_present: bool = False
    artist_present: bool = False
    album_present: bool = False
    date_present: bool = False
    success: bool = True


@dataclass
class ThumbnailValidationResult:
    embedded: bool = False
    saved: bool = False
    success: bool = True


@dataclass
class MetadataValidationResult:
    embedded: bool = False
    chapter_count: int = 0
    success: bool = True


@dataclass
class DownloadValidationResult:
    primary_output: Path | None = None
    subtitle: SubtitleValidationResult = field(default_factory=SubtitleValidationResult)
    audio: AudioValidationResult | None = None
    thumbnail: ThumbnailValidationResult | None = None
    metadata: MetadataValidationResult | None = None
    success: bool = True
    error_code: str = ""
    error_message: str = ""

    def add_error(self, code: str, message: str) -> None:
        """Add an error without failing the entire validation immediately if not terminal, or just standardized logging."""
        self.success = False
        if not self.error_code:
            self.error_code = code
        if not self.error_message:
            self.error_message = message
        else:
            self.error_message += f"\n{message}"

    def fail(self, code: str, message: str) -> None:
        """Mark the validation as immediately failed with a specific terminal error."""
        self.success = False
        self.error_code = code
        self.error_message = message
