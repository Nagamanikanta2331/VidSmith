from mediaforge.downloader.job import DownloadMediaType, SubtitleMode
from mediaforge.downloader.validators.context import ValidationContext
from mediaforge.downloader.validators.models import (
    DownloadValidationResult,
    SubtitleValidationResult,
    ValidationErrorCode,
)
from mediaforge.subtitle import base_language


def validate_subtitles(ctx: ValidationContext, validation: DownloadValidationResult) -> None:
    if ctx.job.subtitle_mode == SubtitleMode.NONE and ctx.job.media_type != DownloadMediaType.TRANSCRIPT:
        return

    embedded: set[str] = set()
    sidecars: set[str] = set()
    subtitle_extensions = {".vtt", ".srt", ".ass", ".lrc", ".ttml"}

    # 1. Check for sidecar files in result.files
    for f in ctx.result.files:
        if f.exists() and f.is_file() and f.suffix.lower() in subtitle_extensions:
            parts = f.suffixes
            if len(parts) >= 2:
                lang = parts[-2].strip(".")
                sidecars.add(base_language(lang))

    # 2. Check primary output for embedded streams
    if ctx.primary_output and ctx.exists:
        if ctx.primary_output.suffix.lower() not in subtitle_extensions:
            if ctx.ffprobe_data:
                for stream in ctx.ffprobe_data.get("streams", []):
                    if stream.get("codec_type") == "subtitle":
                        lang = stream.get("tags", {}).get("language")
                        if lang:
                            embedded.add(base_language(lang))
        else:
            # If the primary file itself is a subtitle (Subtitle Only mode)
            parts = ctx.primary_output.suffixes
            if len(parts) >= 2:
                lang = parts[-2].strip(".")
                sidecars.add(base_language(lang))

    downloaded = list(embedded | sidecars)

    # 3. Calculate failures against job.subtitle_languages
    requested_base = [
        base_language(lang)
        for lang in (ctx.job.subtitle_requested_languages or ctx.job.subtitle_languages)
        if lang.strip()
    ]
    failed: dict[str, str] = {}
    for lang in requested_base:
        if lang not in downloaded:
            failed[lang] = "Unavailable"

    # Merge any explicit yt-dlp failures if they didn't magically download anyway
    for lang, reason in ctx.result.subtitles_failed.items():
        base = base_language(lang)
        if base not in downloaded:
            failed[base] = reason

    # 4. Determine subtitle success
    success = True
    if ctx.job.media_type == DownloadMediaType.TRANSCRIPT and not sidecars:
        success = False

    validation.subtitle = SubtitleValidationResult(
        downloaded_languages=sorted(downloaded),
        embedded_languages=sorted(embedded),
        sidecar_languages=sorted(sidecars),
        failed_languages=failed,
        success=success,
    )
    if not success:
        validation.fail(ValidationErrorCode.TRANSCRIPT_FAILED, "Validation failed: Transcript download failed to produce a sidecar file.")
        return

    # Validate EMBED mode success
    if ctx.job.subtitle_mode in {SubtitleMode.AUTO, SubtitleMode.MANUAL, SubtitleMode.BOTH}:
        for lang in getattr(ctx.result, "subtitles_downloaded", []):
            base = base_language(lang)
            if base not in embedded:
                validation.fail(
                    ValidationErrorCode.SUBTITLE_MISSING,
                    f"Validation failed: Subtitle '{lang}' failed to embed in {ctx.primary_output.name if ctx.primary_output else 'output'}. Temporary files preserved."
                )
                return
