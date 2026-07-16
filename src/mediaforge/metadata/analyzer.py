"""
URL analysis: calls yt-dlp to resolve metadata and determine MediaType.
No downloading takes place here — extract_flat=True is used throughout.
"""

from __future__ import annotations

import re
from typing import Any

import yt_dlp

from mediaforge.models.media import AnalysisResult, AudioStreamInfo, MediaItem, MediaType
from mediaforge.utils.exceptions import AnalysisError, UnsupportedURLError
from mediaforge.utils.validators import is_shorts_url, is_youtube_url

_COMMON_OPTS: dict = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
}


def _seconds(duration: object) -> int:
    try:
        if duration is None or duration == "":
            return 0
        if isinstance(duration, int):
            return duration
        if isinstance(duration, float):
            return int(duration)
        return int(str(duration))
    except (TypeError, ValueError):
        return 0


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _unique_text(values: list[Any]) -> list[str]:
    return sorted({_text(value) for value in values if _text(value)})


def _format_resolution(item: dict) -> str:
    resolution = _text(item.get("resolution"))
    if resolution and resolution != "audio only":
        return resolution

    width = _seconds(item.get("width"))
    height = _seconds(item.get("height"))
    if width and height:
        return f"{width}x{height}"
    if height:
        return f"{height}p"
    return ""


def _resolution_sort_key(resolution: str) -> tuple[int, str]:
    match = re.search(r"(\d+)\s*p?$", resolution.lower())
    if match:
        return int(match.group(1)), resolution

    dimensions = re.match(r"(\d+)\s*x\s*(\d+)", resolution.lower())
    if dimensions:
        return int(dimensions.group(2)), resolution

    return 0, resolution


def _analysis_capabilities(info: dict) -> dict[str, Any]:
    formats = info.get("formats")
    if not isinstance(formats, list):
        formats = []

    resolutions: list[str] = []
    containers: list[object] = []
    video_codecs: list[object] = []
    audio_codecs: list[object] = []
    audio_languages: list[object] = []
    audio_streams: list[AudioStreamInfo] = []
    best_video_size = 0
    best_audio_size = 0

    for item in formats:
        if not isinstance(item, dict):
            continue

        video_codec = _text(item.get("vcodec"))
        audio_codec = _text(item.get("acodec"))
        has_video = video_codec not in {"", "none"}
        has_audio = audio_codec not in {"", "none"}
        size = item.get("filesize") or item.get("filesize_approx") or 0

        if has_video:
            resolutions.append(_format_resolution(item))
            containers.append(item.get("container") or item.get("ext"))
            video_codecs.append(video_codec)
            if size > best_video_size:
                best_video_size = size

        if has_audio:
            containers.append(item.get("container") or item.get("ext"))
            audio_codecs.append(audio_codec)
            lang = item.get("language")
            if lang and lang != "none":
                audio_languages.append(str(lang))
            if size > best_audio_size:
                best_audio_size = size
            # Audio-only streams become selectable wizard entries.
            if not has_video:
                try:
                    bitrate = float(item.get("abr") or item.get("tbr") or 0)
                except (TypeError, ValueError):
                    bitrate = 0.0
                audio_streams.append(
                    AudioStreamInfo(
                        format_id=_text(item.get("format_id")),
                        codec=audio_codec,
                        bitrate=bitrate,
                        language=_text(item.get("language")),
                        sample_rate=_seconds(item.get("asr")),
                        filesize=_seconds(size),
                    )
                )

    subtitles = info.get("subtitles")
    automatic_subtitles = info.get("automatic_captions")

    return {
        "resolutions": sorted(_unique_text(resolutions), key=_resolution_sort_key, reverse=True),
        "containers": _unique_text(containers),
        "video_codecs": _unique_text(video_codecs),
        "audio_codecs": _unique_text(audio_codecs),
        "subtitle_languages": _language_keys(subtitles),
        "automatic_subtitle_languages": _language_keys(automatic_subtitles),
        "audio_languages": _unique_text(audio_languages),
        "audio_streams": sorted(audio_streams, key=lambda s: s.bitrate, reverse=True),
        "estimated_file_size": best_video_size + best_audio_size,
    }


def _language_keys(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    return sorted(str(language) for language in value if language)


def analyze(url: str) -> AnalysisResult:
    """
    Resolve *url* via yt-dlp and return a fully-populated AnalysisResult.
    Raises UnsupportedURLError when the URL is not a recognised YouTube link.
    Raises AnalysisError on any yt-dlp failure.
    """
    url = url.strip()
    if not is_youtube_url(url):
        raise UnsupportedURLError(f"Not a recognised YouTube URL: {url!r}")

    opts = {
        **_COMMON_OPTS,
        "extract_flat": "in_playlist",
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        raise AnalysisError(str(exc)) from exc

    if info is None:
        raise AnalysisError("yt-dlp returned no information for the URL.")

    return _build_result(url, info)


def _build_result(url: str, info: dict) -> AnalysisResult:
    entry_type = info.get("_type", "video")

    if entry_type == "playlist":
        return _playlist_result(url, info)

    if is_shorts_url(url) or "/shorts/" in info.get("webpage_url", ""):
        media_type = MediaType.SHORTS
    else:
        media_type = MediaType.VIDEO

    return AnalysisResult(
        url=url,
        media_type=media_type,
        title=info.get("title", "Unknown"),
        uploader=info.get("uploader", "Unknown"),
        thumbnail_url=info.get("thumbnail", ""),
        duration=_seconds(info.get("duration")),
        view_count=_seconds(info.get("view_count")),
        upload_date=_text(info.get("upload_date")),
        video_id=_text(info.get("id")),
        **_analysis_capabilities(info),
    )


def _playlist_result(url: str, info: dict) -> AnalysisResult:
    entries = info.get("entries") or []
    items = [
        MediaItem(
            url=e.get("url") or e.get("webpage_url") or "",
            title=e.get("title", "Unknown"),
            duration=_seconds(e.get("duration")),
            uploader=e.get("uploader", ""),
            thumbnail_url=e.get("thumbnail", ""),
        )
        for e in entries
    ]
    return AnalysisResult(
        url=url,
        media_type=MediaType.PLAYLIST,
        title=info.get("title", "Unknown Playlist"),
        uploader=info.get("uploader") or info.get("channel", "Unknown"),
        item_count=len(items),
        items=items,
    )
