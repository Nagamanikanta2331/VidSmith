"""Centralized validation layer for downloaded artifacts."""

from __future__ import annotations

from pathlib import Path

from vidsmith.downloader.job import DownloadJob, DownloadMediaType
from vidsmith.downloader.validators import DownloadValidationResult, build_context
from vidsmith.downloader.validators.audio import validate_audio
from vidsmith.downloader.validators.file import validate_files
from vidsmith.downloader.validators.metadata import validate_metadata
from vidsmith.downloader.validators.subtitle import validate_subtitles
from vidsmith.downloader.validators.thumbnail import validate_thumbnail
from vidsmith.providers.results import DownloadResult

VALIDATORS = (
    validate_files,
    validate_metadata,
    validate_thumbnail,
    validate_subtitles,
    validate_audio,
)


_SIDECAR_EXTENSIONS = {
    ".vtt",
    ".srt",
    ".ass",
    ".ssa",
    ".lrc",
    ".ttml",
    ".srv1",
    ".srv2",
    ".srv3",
    ".json3",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".json",
}


def _get_primary_output(
    files: list[Path], media_type: DownloadMediaType | None = None
) -> Path | None:
    if not files:
        return None

    # For VIDEO and AUDIO downloads, the primary output MUST be a real media file.
    # Never fall back to image or subtitle sidecars.
    if media_type in (DownloadMediaType.VIDEO, DownloadMediaType.AUDIO):
        for path in files:
            if (
                path.exists()
                and path.is_file()
                and path.suffix.lower() not in _SIDECAR_EXTENSIONS
            ):
                return path
        return None

    # For THUMBNAIL jobs, prefer image files
    if media_type == DownloadMediaType.THUMBNAIL:
        for path in files:
            if (
                path.exists()
                and path.is_file()
                and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            ):
                return path

    # For SUBTITLE / TRANSCRIPT jobs, prefer caption files
    if media_type in (DownloadMediaType.SUBTITLE, DownloadMediaType.TRANSCRIPT):
        for path in files:
            if (
                path.exists()
                and path.is_file()
                and path.suffix.lower() in {".vtt", ".srt", ".ass", ".txt", ".json"}
            ):
                return path

    # General fallback: prefer non-sidecar media files
    for path in files:
        if (
            path.exists()
            and path.is_file()
            and path.suffix.lower() not in _SIDECAR_EXTENSIONS
        ):
            return path
    for path in files:
        if path.exists() and path.is_file():
            return path
    return files[0]


def validate_download(job: DownloadJob, result: DownloadResult) -> DownloadValidationResult:
    """Validate all requested artifacts for a completed download."""
    primary = _get_primary_output(result.files, job.media_type)
    validation = DownloadValidationResult(primary_output=primary)

    # 1. Build immutable validation context
    ctx = build_context(job, result, primary)

    # 2. Run validator pipeline
    for validator in VALIDATORS:
        validator(ctx, validation)
        if not validation.success:
            break

    return validation
