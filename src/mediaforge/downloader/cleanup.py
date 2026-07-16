"""Centralized cleanup manager for MediaForge."""

from __future__ import annotations

import re
from pathlib import Path

from mediaforge.downloader.job import DownloadJob, MetadataMode, SubtitleMode, ThumbnailMode
from mediaforge.downloader.validator import DownloadValidationResult

# Containers that cannot hold embedded cover art (yt-dlp EmbedThumbnail).
# For these, an EMBED request degrades to "save the thumbnail next to the
# file", so cleanup must keep the image instead of deleting it.
_NO_THUMBNAIL_EMBED = {".ts", ".webm", ".avi", ".flv", ".wav"}




def cleanup_job_artifacts(
    job: DownloadJob,
    final_files: list[Path],
    validation: DownloadValidationResult | None = None,
    *,
    cleanup_enabled: bool = True,
    keep_temp_files: bool = False,
) -> list[Path]:
    """
    Centralized cleanup manager.
    Automatically deletes .part, .temp, .webp, .vtt, .info.json
    ONLY if embedded successfully or user did not explicitly request to keep them.
    """
    deleted_files: list[Path] = []

    if not cleanup_enabled or keep_temp_files:
        return deleted_files

    if not final_files:
        return deleted_files

    for final_file in final_files:
        if not final_file.exists():
            continue

        base_dir = final_file.parent
        base_name = final_file.stem
        embedded_subs = set(validation.subtitle.embedded_languages) if validation and validation.subtitle else set()
        thumb_embedded = validation.thumbnail.embedded if validation and validation.thumbnail else False

        try:
            for item in base_dir.iterdir():
                if not item.is_file():
                    continue

                if item == final_file:
                    continue

                # Match files starting with the same base name prefix
                if item.name.startswith(base_name):
                    suffix = item.suffix.lower()

                    # 1. Part/temp/ytdl/tmp files: always delete
                    if suffix in {".part", ".temp", ".ytdl", ".tmp"} or re.search(
                        r"\.f\d+\.", item.name
                    ):
                        try:
                            item.unlink()
                            deleted_files.append(item)
                        except OSError:
                            pass

                    # 3. Subtitles: delete if embedded only (AUTO/MANUAL) or none selected
                    elif suffix in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}:
                        if job.subtitle_mode == SubtitleMode.NONE:
                            try:
                                item.unlink()
                                deleted_files.append(item)
                            except OSError:
                                pass
                        elif job.subtitle_mode in {SubtitleMode.AUTO, SubtitleMode.MANUAL, SubtitleMode.BOTH}:
                            # Only delete if it actually got embedded
                            parts = item.suffixes
                            if len(parts) >= 2:
                                lang = parts[-2].strip(".")
                                if any(e.startswith(lang) for e in embedded_subs):
                                    try:
                                        item.unlink()
                                        deleted_files.append(item)
                                    except OSError:
                                        pass

                    # 4. Thumbnails: delete if embedded or none selected.
                    #    When the final container cannot embed cover art
                    #    (webm/wav), EMBED degraded to a sidecar save — keep it.
                    elif (
                        suffix in {".webp", ".jpg", ".png", ".jpeg"}
                        and job.thumbnail_mode in {ThumbnailMode.EMBED, ThumbnailMode.NONE}
                        and not (
                            job.thumbnail_mode == ThumbnailMode.EMBED
                            and final_file.suffix.lower() in _NO_THUMBNAIL_EMBED
                        )
                    ):
                        # ONLY delete if we verified it embedded successfully (or if we skipped embedding)
                        if thumb_embedded is True or job.thumbnail_mode == ThumbnailMode.NONE:
                            try:
                                item.unlink()
                                deleted_files.append(item)
                            except OSError:
                                pass

                    elif (
                        suffix == ".json"
                        and item.name.endswith(".info.json")
                        and job.metadata_mode in {MetadataMode.EMBED, MetadataMode.NONE}
                    ):
                        try:
                            item.unlink()
                            deleted_files.append(item)
                        except OSError:
                            pass
        except OSError:
            pass

    return deleted_files
