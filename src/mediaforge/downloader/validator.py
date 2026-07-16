"""Centralized validation layer for downloaded artifacts."""

from __future__ import annotations

from pathlib import Path

from mediaforge.downloader.job import DownloadJob
from mediaforge.downloader.validators import DownloadValidationResult, build_context
from mediaforge.downloader.validators.audio import validate_audio
from mediaforge.downloader.validators.file import validate_files
from mediaforge.downloader.validators.metadata import validate_metadata
from mediaforge.downloader.validators.subtitle import validate_subtitles
from mediaforge.downloader.validators.thumbnail import validate_thumbnail
from mediaforge.providers.results import DownloadResult

VALIDATORS = (
    validate_files,
    validate_metadata,
    validate_thumbnail,
    validate_subtitles,
    validate_audio,
)


def _get_primary_output(files: list[Path]) -> Path | None:
    if not files:
        return None
    # Prefer non-sidecar media files as primary
    for path in files:
        if (
            path.exists()
            and path.is_file()
            and path.suffix.lower()
            not in {".vtt", ".srt", ".ass", ".lrc", ".ttml", ".jpg", ".png", ".webp", ".json"}
        ):
            return path
    # Fallback to the first existing file
    for path in files:
        if path.exists() and path.is_file():
            return path
    return files[0]


def validate_download(job: DownloadJob, result: DownloadResult) -> DownloadValidationResult:
    """Validate all requested artifacts for a completed download."""
    primary = _get_primary_output(result.files)
    validation = DownloadValidationResult(primary_output=primary)

    # 1. Build immutable validation context
    ctx = build_context(job, result, primary)

    # 2. Run validator pipeline
    for validator in VALIDATORS:
        validator(ctx, validation)
        if not validation.success:
            break

    return validation
