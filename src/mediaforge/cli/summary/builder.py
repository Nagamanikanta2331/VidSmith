from pathlib import Path

from mediaforge.cli.summary.model import SummaryModel
from mediaforge.downloader.job import DownloadJob, MetadataMode, SubtitleMode, ThumbnailMode
from mediaforge.downloader.validators.models import DownloadValidationResult
from mediaforge.models.media import AnalysisResult
from mediaforge.providers.results import DownloadResult
from mediaforge.subtitle import base_language

# Duplicated from executor or shared
_LANG_DISPLAY = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "hi": "Hindi", "te": "Telugu", "ta": "Tamil", "ml": "Malayalam",
    "bn": "Bengali", "mr": "Marathi", "pa": "Punjabi", "ar": "Arabic",
    "zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)",
    "ja": "Japanese", "ko": "Korean", "pt": "Portuguese", "ru": "Russian",
    "tr": "Turkish", "vi": "Vietnamese", "th": "Thai", "pl": "Polish",
    "id": "Indonesian", "it": "Italian",
}

def _lang_name(code: str) -> str:
    return _LANG_DISPLAY.get(code, _LANG_DISPLAY.get(code.split("-")[0], code))

def _quality_label(quality: str) -> str:
    normalized = quality.strip().lower()
    labels = {
        "best": "Best available", "highest": "Best available",
        "2160": "2160p (4K)", "2160p": "2160p (4K)",
        "1440": "1440p (2K)", "1440p": "1440p (2K)",
        "1080": "1080p (HD)", "1080p": "1080p (HD)",
        "720": "720p (HD)", "720p": "720p (HD)",
    }
    return labels.get(normalized, quality)


def _files_size(files: list[Path]) -> int:
    total = 0
    for path in files:
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            continue
    return total


def build_summary(
    job: DownloadJob,
    dl_result: DownloadResult,
    validation: DownloadValidationResult,
    download_seconds: float,
    analysis: AnalysisResult | None = None,
) -> SummaryModel:
    files = getattr(dl_result, "files", []) or []
    primary_file = validation.primary_output
    location = primary_file.parent if primary_file is not None else job.output_dir
    file_name = primary_file.name if primary_file is not None else "(output directory)"
    file_size = _files_size(files)
    metadata = getattr(dl_result, "metadata", {}) or {}

    model = SummaryModel(
        title=metadata.get("title") or (analysis.title if analysis else ""),
        channel=metadata.get("channel") or (analysis.uploader if analysis else ""),
        file_name=file_name,
        output_folder=str(location),
        container=(metadata.get("format") or (job.audio_format if job.is_audio else job.video_format)).upper(),
        video_quality=_quality_label(job.quality) if not job.is_audio else "Audio only",
        resolution=metadata.get("resolution"),
        fps=metadata.get("fps"),
        hdr=metadata.get("hdr"),
        video_codec=metadata.get("video_codec"),
        video_bitrate=metadata.get("video_bitrate"),
        audio_codec=metadata.get("audio_codec"),
        audio_bitrate=metadata.get("audio_bitrate"),
        audio_language=metadata.get("audio_language"),
        file_size_bytes=file_size,
        duration_seconds=metadata.get("duration") or (analysis.duration if analysis else 0),
        download_seconds=download_seconds,
    )

    # Features
    if job.metadata_mode == MetadataMode.EMBED and validation.metadata:
        if validation.metadata.embedded:
            model.features.append(("Metadata", "[green]✓[/] Embedded"))
        if validation.metadata.chapter_count > 0:
            model.features.append(("Chapters", f"[green]✓[/] Embedded ({validation.metadata.chapter_count})"))

    if job.thumbnail_mode != ThumbnailMode.NONE and validation.thumbnail:
        if validation.thumbnail.saved and not validation.thumbnail.embedded:
            model.features.append(("Thumbnail", "[green]✓[/] Saved separately"))
        elif validation.thumbnail.embedded:
            model.features.append(("Thumbnail", "[green]✓[/] Embedded"))
            if validation.thumbnail.saved:
                model.features.append(("Thumbnail", "[green]✓[/] Saved separately"))
        elif not validation.thumbnail.success:
            model.features.append(("Thumbnail", "[red]✗[/] Embedding failed.\nThumbnail saved separately."))

    if validation.audio and validation.audio.artwork_status != "Unsupported":
        model.features.append(("Audio Artwork", f"[green]✓[/] {validation.audio.artwork_status}"))

    if validation.audio:
        md_status = []
        if validation.audio.title_present:
            md_status.append("Title")
        if validation.audio.artist_present:
            md_status.append("Artist")
        if validation.audio.album_present:
            md_status.append("Album")
        if validation.audio.date_present:
            md_status.append("Date")
        if md_status:
            model.features.append(("Audio Metadata", "[green]✓[/] " + ", ".join(md_status)))
        else:
            model.features.append(("Audio Metadata", "[red]✗[/] Missing"))

    model.features.append(("Resume", "[green]✓[/] Supported"))

    # Subtitles
    if job.subtitle_mode != SubtitleMode.NONE and validation.subtitle:
        requested = [base_language(lang) for lang in (job.subtitle_requested_languages or job.subtitle_languages) if lang.strip()]
        for lang in requested:
            name = _lang_name(lang)
            if lang in validation.subtitle.failed_languages:
                model.subtitles.append((f"{name} ({lang})", f"[red]✗[/] {validation.subtitle.failed_languages[lang]}"))
            elif lang in validation.subtitle.embedded_languages:
                model.subtitles.append((f"{name} ({lang})", "[green]✓[/] Embedded"))
            elif lang in validation.subtitle.sidecar_languages:
                model.subtitles.append((f"{name} ({lang})", "[green]✓[/] Downloaded (sidecar)"))

    return model
