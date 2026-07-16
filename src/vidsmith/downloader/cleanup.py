"""Centralized cleanup manager for VidSmith."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from vidsmith.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    ThumbnailMode,
)
from vidsmith.downloader.validator import DownloadValidationResult

# Sidecar extensions produced by yt-dlp that are only ever scaffolding for
# embedding into the final media file. yt-dlp writes several YouTube-native
# caption containers (srv1/srv2/srv3/json3) in addition to the standard
# formats, and every one of them must be swept.
_SUBTITLE_SUFFIXES = {
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
}
_THUMBNAIL_SUFFIXES = {".webp", ".jpg", ".jpeg", ".png"}
_ALWAYS_TEMP_SUFFIXES = {".part", ".temp", ".ytdl", ".tmp"}

# Media whose deliverable IS a subtitle/caption file — never delete those.
_SUBTITLE_DELIVERABLE = {DownloadMediaType.SUBTITLE, DownloadMediaType.TRANSCRIPT}

# Containers that cannot hold embedded cover art (yt-dlp EmbedThumbnail).
# For these, an EMBED request degrades to "save the thumbnail next to the
# file", so cleanup must keep the image instead of deleting it.
_NO_THUMBNAIL_EMBED = {".ts", ".webm", ".avi", ".flv", ".wav"}


def _norm(text: str) -> str:
    """Unicode-normalise for reliable prefix matching.

    A title with an emoji or accent can be stored as NFC on one filesystem and
    NFD on another; yt-dlp may also write the media file and its sidecars with
    different normalisation. Comparing raw bytes then fails and the sidecar is
    orphaned. Casefolding + NFC makes the match device-independent.
    """
    return unicodedata.normalize("NFC", text).casefold()


def cleanup_job_artifacts(
    job: DownloadJob,
    final_files: list[Path],
    validation: DownloadValidationResult | None = None,
    *,
    cleanup_enabled: bool = True,
    keep_temp_files: bool = False,
) -> list[Path]:
    """Remove transient artifacts left beside a finished download.

    Cleanup only runs after validation has already confirmed the download
    succeeded, so it does not re-verify embedding: for a video/audio file any
    leftover subtitle or thumbnail sidecar is scaffolding and is deleted
    unconditionally. Files that are themselves the deliverable — a subtitle or
    transcript job's caption files, a thumbnail job's image, or a thumbnail
    kept via SAVE/BOTH — are preserved.
    """
    deleted_files: list[Path] = []

    if not cleanup_enabled or keep_temp_files:
        return deleted_files

    if not final_files:
        return deleted_files

    # Deleting a sidecar once is enough even when several final files share a
    # directory; track by resolved path to stay idempotent across final_files.
    # Whether a file is a deliverable to preserve is decided by _should_delete
    # (media type / thumbnail mode) — NOT by membership in final_files, because
    # yt-dlp lists transient sidecars (the thumbnail it embedded) there too.
    seen: set[Path] = set()

    for final_file in final_files:
        if not final_file.exists():
            continue

        base_dir = final_file.parent
        base_prefix = _norm(final_file.stem)
        final_suffix = final_file.suffix.lower()
        anchor = _safe_resolve(final_file)

        try:
            entries = list(base_dir.iterdir())
        except OSError:
            continue

        for item in entries:
            resolved = _safe_resolve(item)
            # Never delete the file we're anchoring the search on.
            if resolved == anchor or resolved in seen:
                continue

            try:
                if not item.is_file():
                    continue
            except OSError:
                continue

            # Only touch files that belong to this download (share the stem),
            # matched normalisation-insensitively so unicode titles still pair
            # with their sidecars across filesystems.
            if not _norm(item.name).startswith(base_prefix):
                continue

            if _should_delete(job, item, final_suffix) and _unlink(item):
                deleted_files.append(item)
                seen.add(resolved)

    return deleted_files


def _should_delete(job: DownloadJob, item: Path, final_suffix: str) -> bool:
    """Decide whether one sidecar next to the final file is disposable."""
    suffix = item.suffix.lower()

    # 1. Part/fragment/temp files: always disposable.
    if suffix in _ALWAYS_TEMP_SUFFIXES or re.search(r"\.f\d+\.", item.name):
        return True

    # 2. Subtitles/captions: transient for video/audio (they exist only to be
    #    embedded). Preserved when the job's product IS the caption file.
    if suffix in _SUBTITLE_SUFFIXES:
        return job.media_type not in _SUBTITLE_DELIVERABLE

    # 3. Thumbnails: disposable when the user asked to embed only (or not at
    #    all). Kept when SAVE/BOTH requested it as a sidecar, when the job is a
    #    standalone thumbnail download, or when the final container cannot embed
    #    cover art (EMBED silently degraded to a sidecar save).
    if suffix in _THUMBNAIL_SUFFIXES:
        keep = (
            job.media_type == DownloadMediaType.THUMBNAIL
            or job.thumbnail_mode in {ThumbnailMode.SAVE, ThumbnailMode.BOTH}
            or (job.thumbnail_mode == ThumbnailMode.EMBED and final_suffix in _NO_THUMBNAIL_EMBED)
        )
        return not keep

    # 4. Sidecar metadata json (…​.info.json): disposable unless the user asked
    #    to keep the metadata file (MetadataMode.SAVE).
    if suffix == ".json" and item.name.endswith(".info.json"):
        return job.metadata_mode in {MetadataMode.EMBED, MetadataMode.NONE}

    return False


def _safe_resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _unlink(item: Path) -> bool:
    try:
        item.unlink()
        return True
    except OSError:
        return False
