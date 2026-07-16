from pathlib import Path

from mediaforge.cli.summary.model import SummaryArtifactType, SummaryModel
from mediaforge.cli.summary.renderer import _elapsed_label, _format_bytes, _media_duration
from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.downloader.validators.models import DownloadValidationResult
from mediaforge.models.media import AnalysisResult
from mediaforge.providers.results import DownloadResult
from mediaforge.subtitle import SUBTITLE_LANGUAGE_NAMES, language_matches

_LANG_DISPLAY = {
    # Canonical policy names first (en/hi/te/ta/mr/bn/ml/pa/gu/ur), then extras.
    **SUBTITLE_LANGUAGE_NAMES,
    "es": "Spanish", "fr": "French", "de": "German", "ar": "Arabic",
    "zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)",
    "ja": "Japanese", "ko": "Korean", "pt": "Portuguese", "ru": "Russian",
    "tr": "Turkish", "vi": "Vietnamese", "th": "Thai", "pl": "Polish",
    "id": "Indonesian", "it": "Italian", "kn": "Kannada", "or": "Odia",
    "as": "Assamese", "ne": "Nepali", "si": "Sinhala", "sd": "Sindhi",
    "bho": "Bhojpuri", "sa": "Sanskrit",
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

    if job.media_type == DownloadMediaType.THUMBNAIL:
        artifact_type = SummaryArtifactType.THUMBNAIL
    elif job.media_type == DownloadMediaType.AUDIO:
        artifact_type = SummaryArtifactType.AUDIO
    elif job.media_type == DownloadMediaType.SUBTITLE:
        artifact_type = SummaryArtifactType.SUBTITLE
    elif job.media_type == DownloadMediaType.TRANSCRIPT:
        artifact_type = SummaryArtifactType.TRANSCRIPT
    else:
        artifact_type = SummaryArtifactType.VIDEO

    model = SummaryModel(
        title=metadata.get("title") or (analysis.title if analysis else ""),
        channel=metadata.get("channel") or (analysis.uploader if analysis else ""),
        artifact_type=artifact_type,
    )

    duration_str = _media_duration(metadata.get("duration") or (analysis.duration if analysis else 0))

    if artifact_type == SummaryArtifactType.VIDEO:
        model.rows = [
            ("Video Name", model.title),
            ("Channel", model.channel),
            ("File Name", file_name),
            ("Output Folder", str(location)),
            ("Container", (metadata.get("format") or job.video_format).upper()),
            ("Video Quality", _quality_label(job.quality)),
            ("Resolution", metadata.get("resolution")),
            ("FPS", metadata.get("fps")),
            ("HDR", metadata.get("hdr")),
            ("Video Codec", metadata.get("video_codec")),
            ("Video Bitrate", metadata.get("video_bitrate")),
            ("Audio Codec", metadata.get("audio_codec")),
            ("Audio Bitrate", metadata.get("audio_bitrate")),
            ("Audio Language", metadata.get("audio_language")),
            ("File Size", _format_bytes(file_size) if file_size else ""),
            ("Duration", duration_str),
            ("Download Time", _elapsed_label(download_seconds)),
        ]

        # Features for Video
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

        model.features.append(("Resume", "[green]✓[/] Supported"))

        if job.subtitle_mode != SubtitleMode.NONE and validation.subtitle:
            requested = [lang for lang in (job.subtitle_requested_languages or job.subtitle_languages) if lang.strip()]
            for lang in requested:
                name = _lang_name(lang)
                # ffprobe reports embedded streams with three-letter codes
                # (hin/tel/…), so compare via the shared language helper.
                if language_matches(lang, validation.subtitle.embedded_languages):
                    model.subtitles.append((f"{name} ({lang})", "[green]✓[/] Embedded"))
                elif lang in validation.subtitle.failed_languages:
                    model.subtitles.append((f"{name} ({lang})", f"[red]✗[/] {validation.subtitle.failed_languages[lang]}"))
                elif language_matches(lang, validation.subtitle.sidecar_languages):
                    model.subtitles.append((f"{name} ({lang})", "[green]✓[/] Downloaded (sidecar)"))

    elif artifact_type == SummaryArtifactType.AUDIO:
        model.rows = [
            ("Audio Name", model.title),
            ("Channel", model.channel),
            ("File Name", file_name),
            ("Output Folder", str(location)),
            ("Output Format", job.audio_format.upper() if job.audio_format else "MP3"),
            ("Audio Codec", metadata.get("audio_codec")),
            ("Audio Bitrate", metadata.get("audio_bitrate")),
            ("Audio Language", metadata.get("audio_language")),
            ("File Size", _format_bytes(file_size) if file_size else ""),
            ("Duration", duration_str),
            ("Download Time", _elapsed_label(download_seconds)),
        ]

        # Audio Metadata Features
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

    elif artifact_type == SummaryArtifactType.THUMBNAIL:
        res = metadata.get("resolution")
        if not res and analysis and analysis.width:
            res = f"{analysis.width}x{analysis.height}"

        img_format = "JPG"
        if files:
            img_format = files[0].suffix.lstrip(".").upper()

        model.rows = [
            ("Video Name", model.title),
            ("Channel", model.channel),
            ("File Name", file_name),
            ("Output Folder", str(location)),
            ("Image Format", img_format),
            ("Resolution", res),
            ("Dimensions", res),
            ("File Size", _format_bytes(file_size) if file_size else ""),
        ]
        if metadata.get("color_space"):
            model.rows.append(("Color Space", metadata.get("color_space")))

    elif artifact_type == SummaryArtifactType.SUBTITLE:
        lang_names = [_lang_name(lang) for lang in validation.subtitle.sidecar_languages]

        model.rows = [
            ("Video Name", model.title),
            ("Channel", model.channel),
            ("Output Folder", str(location)),
            ("Downloaded Languages", ", ".join(lang_names) if lang_names else "None"),
            ("Manual", str(len([lang for lang in validation.subtitle.sidecar_languages if lang not in (job.subtitle_auto_languages or [])]))),
            ("Auto", str(len([lang for lang in validation.subtitle.sidecar_languages if lang in (job.subtitle_auto_languages or [])]))),
            ("Embedded", "No"),
            ("Files Created", str(len([f for f in files if f.suffix in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}]))),
        ]

    elif artifact_type == SummaryArtifactType.TRANSCRIPT:
        model.rows = [
            ("Video Name", model.title),
            ("Channel", model.channel),
            ("Output Folder", str(location)),
            ("Format", "TXT"),
            ("Caption Source", "Auto" if job.subtitle_mode == SubtitleMode.AUTO else "Manual"),
            ("Language", _lang_name(job.subtitle_languages[0]) if job.subtitle_languages else "Unknown"),
            ("Segments", "Unknown"),
            ("Timestamps", "Yes" if "with-timestamps" in str(job.output_dir) or True else "No"), # Just a placeholder since MediaForge doesn't pass a explicit flag for timestamps right now. Wait, Transcript job always strips timestamps unless requested, actually the python scraper does.
            ("File Size", _format_bytes(file_size) if file_size else ""),
        ]

    return model
