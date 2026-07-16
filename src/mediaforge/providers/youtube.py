"""YouTube provider stub for the downloader architecture."""

from __future__ import annotations

import re
import typing
from collections.abc import Iterable
from pathlib import Path
from shutil import which
from typing import Any

from yt_dlp import YoutubeDL

from mediaforge.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    JobStatus,
    SubtitleMode,
    ThumbnailMode,
)
from mediaforge.downloader.progress import (
    DownloadProgress,
    DownloadStage,
    ProgressCallback,
    stage_label,
)
from mediaforge.providers.base import Provider
from mediaforge.providers.capabilities import (
    AudioFormatOption,
    FormatOptions,
    SubtitleLanguageOption,
    SubtitleOptions,
    ThumbnailOption,
    VideoFormatOption,
)
from mediaforge.providers.metadata import (
    AudioFormatMetadata,
    ProviderMediaType,
    ThumbnailMetadata,
    VideoFormatMetadata,
    YouTubeMetadata,
)
from mediaforge.providers.results import DownloadResult, DownloadResultStatus
from mediaforge.subtitle import is_supported_language
from mediaforge.utils.environment import js_runtimes_option
from mediaforge.utils.exceptions import AnalysisError, DownloadError, UnsupportedURLError
from mediaforge.utils.validators import is_youtube_url


class _DownloadCancelled(Exception):
    """Internal signal used to stop yt-dlp from a progress hook."""


class _SubtitleLogger:
    """Silent yt-dlp logger that records subtitle-download failures.

    yt-dlp reports a failed subtitle language as a *warning* (never fatal), e.g.
    ``Unable to download video subtitles for 'ar': HTTP Error 429``.  We capture
    those so the summary can list which languages failed and why, without
    un-suppressing the rest of yt-dlp's chatter.
    """

    _SUB_WARNING = re.compile(
        r"[Uu]nable to download.*?subtitles?(?: for)? ['\"]?([A-Za-z][\w-]*)['\"]?\s*[:\-]?\s*(.*)"
    )

    def __init__(self) -> None:
        self.subtitle_failures: dict[str, str] = {}
        import logging
        self.logger = logging.getLogger("mediaforge.subtitle")

    def _record(self, message: str) -> None:
        match = self._SUB_WARNING.search(message)
        if not match:
            return
        lang = match.group(1)
        reason = (match.group(2) or "").strip()
        classified = _classify_subtitle_reason(reason)
        self.subtitle_failures[lang] = classified
        self.logger.warning(f"Subtitle '{lang}' failed: {classified} ({reason})")

    # yt-dlp calls debug/info/warning/error on its logger.
    def debug(self, message: str) -> None:
        if message and not message.startswith("[debug]"):
            self._record(message)

    def info(self, message: str) -> None:
        self._record(message)

    def warning(self, message: str) -> None:
        self._record(message)

    def error(self, message: str) -> None:
        self._record(message)


def _classify_subtitle_reason(reason: str) -> str:
    """Turn a raw yt-dlp subtitle error into a short, human-readable reason."""
    lowered = reason.lower()
    if "429" in lowered or "too many requests" in lowered:
        return "HTTP 429 (Rate Limited)"
    if "404" in lowered or "not found" in lowered or "no closed captions" in lowered:
        return "Unavailable"
    if "timed out" in lowered or "timeout" in lowered:
        return "Timeout"
    return reason.split(":")[0].strip().capitalize() if reason else "Unknown"


class YouTubeProvider(Provider):
    """Concrete Provider shell for future YouTube download integration."""

    _VP9_OPUS_FORMAT_CHAIN = "313+251/308+251/303+251/302+251"
    _VP9_HEIGHT_FORMATS = {
        2160: "313",
        1440: "308",
        1080: "303",
        720: "302",
    }
    _VP9_OPUS_AUDIO = "251"

    def __init__(self, config: dict[str, Any] | None = None, client: object | None = None) -> None:
        self.config = config or {}
        self.client = client
        self._metadata_cache: dict[str, dict[str, Any]] = {}
        self._metadata_cache_size = int(self.config.get("metadata_cache_size", 16))

    def analyze(self, url: str) -> YouTubeMetadata:
        """Retrieve and normalize YouTube metadata without downloading media."""
        normalized_url, info = self._get_metadata(url)
        return self._normalize_metadata(normalized_url, info)

    def get_formats(self, url: str) -> FormatOptions:
        """Return normalized downloadable audio/video format options."""
        _, info = self._get_metadata(url)
        video_formats, audio_formats = self._normalize_capability_formats(info.get("formats"))
        return FormatOptions(video=video_formats, audio=audio_formats)

    def get_subtitles(self, url: str) -> SubtitleOptions:
        """Return normalized manual and automatic subtitle options."""
        _, info = self._get_metadata(url)
        return SubtitleOptions(
            manual=self._normalize_subtitle_languages(info.get("subtitles")),
            automatic=self._normalize_subtitle_languages(info.get("automatic_captions")),
        )

    def get_thumbnail_options(self, url: str) -> list[ThumbnailOption]:
        """Return all normalized thumbnail options from highest quality to lowest."""
        _, info = self._get_metadata(url)
        thumbnails = self._normalize_thumbnail_options(info.get("thumbnails"))
        return sorted(thumbnails, key=self._thumbnail_sort_key, reverse=True)

    def get_thumbnail(self, url: str) -> str | None:
        """Return the best thumbnail URL for a video."""
        options = self.get_thumbnail_options(url)
        return options[0].url if options else None

    def download(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download a single video job through the official yt-dlp Python API."""
        return self._run_download(
            job=job,
            progress_callback=progress_callback,
            options=self._build_download_options(job, progress_callback),
            media_type="video",
        )

    def download_audio(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download or convert a single audio job through the yt-dlp Python API."""
        return self._run_download(
            job=job,
            progress_callback=progress_callback,
            options=self._build_download_options(job, progress_callback),
            media_type="audio",
        )

    def download_subtitles(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download subtitle files without downloading media."""
        subtitle_job = self._artifact_job(job)
        if subtitle_job.subtitle_mode == SubtitleMode.NONE:
            subtitle_job.subtitle_mode = SubtitleMode.BOTH
        return self._run_download(
            job=subtitle_job,
            progress_callback=progress_callback,
            options=self._build_download_options(subtitle_job, progress_callback),
            media_type="subtitles",
        )

    def download_thumbnail(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download the best thumbnail without downloading media."""
        thumbnail_job = self._artifact_job(job)
        thumbnail_job.thumbnail_mode = ThumbnailMode.SAVE
        return self._run_download(
            job=thumbnail_job,
            progress_callback=progress_callback,
            options=self._build_download_options(thumbnail_job, progress_callback),
            media_type="thumbnail",
        )

    def download_transcript(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None = None,
    ) -> DownloadResult:
        """Download subtitle source files for transcript conversion."""
        return self.download_subtitles(job, progress_callback=progress_callback)

    def _metadata_options(self) -> dict[str, Any]:
        options = {
            **self.config.get("metadata_options", {}),
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "simulate": True,
            "extract_flat": "in_playlist",
        }
        return options

    def _run_download(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
        options: dict[str, Any],
        media_type: str,
    ) -> DownloadResult:
        normalized_url = job.url.strip()
        if not is_youtube_url(normalized_url):
            raise UnsupportedURLError(f"Not a recognized YouTube URL: {job.url!r}")
        if job.is_playlist:
            raise DownloadError("Playlist downloading is not implemented yet.")

        job.output_dir.mkdir(parents=True, exist_ok=True)
        attempts = int(self.config.get("download_retries", 3))
        last_error = ""

        # Records per-language subtitle failures (warnings, never fatal) so the
        # summary can report them instead of losing them to yt-dlp's silence.
        # A custom logger only receives warnings when no_warnings is False; the
        # logger itself stays silent, so the console output is unchanged.
        subtitle_logger = _SubtitleLogger()
        run_options = {**options, "logger": subtitle_logger, "no_warnings": False}

        for attempt in range(1, attempts + 1):
            try:
                self._raise_if_cancelled(job)
                self._emit_stage(progress_callback, job, DownloadStage.EXTRACTING)
                self._emit_stage(progress_callback, job, DownloadStage.SELECTING)
                with YoutubeDL(typing.cast(typing.Any, run_options)) as ydl:
                    raw_info = ydl.extract_info(normalized_url, download=True)
                    info = ydl.sanitize_info(raw_info)
            except _DownloadCancelled:
                self._cleanup_after_cancellation(job)
                return DownloadResult(
                    job_id=job.job_id,
                    url=normalized_url,
                    status=DownloadResultStatus.CANCELLED,
                    output_dir=job.output_dir,
                    media_type=media_type,
                    message=stage_label(DownloadStage.CANCELLED),
                )
            except Exception as exc:
                last_error = str(exc)
                if attempt >= attempts:
                    raise DownloadError(
                        f"YouTube {media_type} download failed after {attempts} attempts: {last_error}"
                    ) from None
                continue

            if not isinstance(info, dict):
                raise DownloadError("YouTube download returned an invalid response.")

            self._remember_metadata(normalized_url, info)
            result = self._download_result(
                job, normalized_url, info, media_type, subtitle_logger.subtitle_failures
            )
            self._emit_progress(
                progress_callback,
                DownloadProgress(
                    job_id=job.job_id,
                    stage=DownloadStage.COMPLETED,
                    percent=100.0,
                    message=stage_label(DownloadStage.COMPLETED),
                ),
            )
            return result

        raise DownloadError(f"YouTube {media_type} download failed: {last_error}")

    def _build_download_options(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, Any]:
        options = self._base_download_options(job, progress_callback)

        # Artifact-only downloads (subtitles/thumbnail only)
        if job.media_type == DownloadMediaType.TRANSCRIPT:
            options.update(
                {
                    "skip_download": True,
                    "format": "best",
                    "embedsubtitles": False,
                    "embedthumbnail": False,
                    "addmetadata": False,
                    "postprocessors": [],
                }
            )
            return options

        # Audio Download
        if job.media_type == DownloadMediaType.AUDIO:
            audio_format = self._normalized_audio_format(job.audio_format)
            options["format"] = self._audio_format_selector(audio_format, getattr(job, "audio_stream_id", ""))
            if audio_format != "original":
                options["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": audio_format,
                        "preferredquality": self._audio_quality(job.audio_quality),
                    },
                    *options.get("postprocessors", []),
                ]
            return options

        # Video Download (Best, Manual, Playlist)
        container = self._normalized_video_container(job.video_format)
        audio_lang = getattr(job, "audio_language", "")
        options["format"] = self._video_format_selector(job.quality, container, audio_lang)
        options["merge_output_format"] = container
        return options

    def _base_download_options(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, Any]:
        options = self._safe_download_defaults() | {
            **self.config.get("download_options", {}),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "nopart": False,
            "overwrites": job.overwrite,
            "outtmpl": self._output_template(job),
            "progress_hooks": [self._progress_hook(job, progress_callback)],
            "postprocessor_hooks": [self._postprocessor_hook(job, progress_callback)],
            "subtitlesformat": "best/vtt",
            "writesubtitles": self._writes_manual_subtitles(job),
            "writeautomaticsub": self._writes_auto_subtitles(job),
            "subtitleslangs": self._subtitle_languages(job),
            "embedsubtitles": False,  # Phase C: Handled by FFmpegProcessor
            "writethumbnail": self._writes_thumbnail(job),
            "embedthumbnail": self._embeds_thumbnail(job),
            "addmetadata": False,  # Phase C: Handled by FFmpegProcessor
            "embed_info_json": False,
            "writeinfojson": False,
            "postprocessors": self._postprocessors(job),
        }
        return options

    def _safe_download_defaults(self) -> dict[str, Any]:
        """Production-safe yt-dlp defaults shared by all download modes."""
        defaults: dict[str, Any] = {
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "file_access_retries": 1,
            "continuedl": True,
            "buffersize": 1024 * 1024,
            "concurrent_fragment_downloads": 5,
            "socket_timeout": 20,
            "http_chunk_size": 10 * 1024 * 1024,
            "progress_delta": 0.2,
            # Ignore download errors (like subtitle HTTP 429) so they don't abort
            # the entire process. The executor will validate the main media files.
            "ignoreerrors": "only_download",
            # Throttling each subtitle request keeps YouTube from rate-limiting
            "sleep_interval_subtitles": int(self.config.get("subtitle_sleep_interval", 1)),
            # Implement 429 retry: Sleep for subtitle_delay_seconds before retrying.
            # file_access_retries=1 limits it to exactly one retry.
            "retry_sleep": {"http": int(self.config.get("subtitle_sleep_interval", 125))},
        }
        # Enable a non-default JS runtime (node/bun) when present so YouTube does
        # not silently drop formats; when only deno exists yt-dlp already uses it.
        js_runtimes = js_runtimes_option(self.config.get("node_path_override", ""))
        if js_runtimes:
            defaults["js_runtimes"] = js_runtimes
        return defaults | self._ffmpeg_location_option()

    def _ffmpeg_location_option(self) -> dict[str, str]:
        configured = self.config.get("ffmpeg_location")
        if configured:
            return {"ffmpeg_location": str(configured)}
        if which("ffmpeg"):
            return {}
        try:
            import imageio_ffmpeg
        except ImportError:
            return {}
        return {"ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe()}

    def _postprocessors(self, job: DownloadJob) -> list[dict[str, Any]]:
        postprocessors: list[dict[str, Any]] = []

        # Phase C: Subtitles and Metadata embedding are now handled by FFmpegProcessor
        # in executor._finalize_download, not yt-dlp.

        if self._embeds_thumbnail(job):
            postprocessors.append(
                {
                    "key": "FFmpegThumbnailsConvertor",
                    "format": "jpg",
                }
            )
            postprocessors.append(
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": self._writes_thumbnail(job),
                }
            )

        return postprocessors

    def _writes_manual_subtitles(self, job: DownloadJob) -> bool:
        return job.subtitle_mode in {SubtitleMode.MANUAL, SubtitleMode.BOTH}

    def _writes_auto_subtitles(self, job: DownloadJob) -> bool:
        return job.subtitle_mode in {SubtitleMode.AUTO, SubtitleMode.BOTH}

    def _embeds_subtitles(self, job: DownloadJob) -> bool:
        return job.media_type == DownloadMediaType.VIDEO and job.subtitle_mode != SubtitleMode.NONE

    def _subtitle_languages(self, job: DownloadJob) -> list[str]:
        """Exact subtitle codes to request from yt-dlp.

        Only the supported languages (en/hi/te/ta) are ever requested; the
        job builders resolve manual-vs-auto beforehand. Translated tracks are
        excluded by never requesting them ("all" is not supported), and a
        trailing "-.*" guards against wildcard expansion.
        """
        languages = [
            lang.strip()
            for lang in job.subtitle_languages
            if lang.strip() and is_supported_language(lang)
        ]
        if not languages:
            return []
        # Always exclude translations
        if "-.*" not in languages:
            languages.append("-.*")
        return languages

    def _writes_thumbnail(self, job: DownloadJob) -> bool:
        return job.thumbnail_mode in {
            ThumbnailMode.EMBED,
            ThumbnailMode.SAVE,
            ThumbnailMode.BOTH,
        }

    # Containers yt-dlp's EmbedThumbnail postprocessor can write cover art into
    # ("Supported filetypes for thumbnail embedding are: mp3, mkv/mka,
    # ogg/opus/flac, m4a/mp4/m4v/mov").  Requesting it for anything else (webm,
    # wav) is a FATAL postprocessing error, not a warning.
    _THUMBNAIL_EMBED_VIDEO = {"mp4", "mkv", "m4v", "mov"}
    _THUMBNAIL_EMBED_AUDIO = {"mp3", "m4a", "opus", "flac", "ogg", "aac", "original"}

    def _container_supports_thumbnail(self, job: DownloadJob) -> bool:
        if job.is_audio:
            return self._normalized_audio_format(job.audio_format) in self._THUMBNAIL_EMBED_AUDIO
        return self._normalized_video_container(job.video_format) in self._THUMBNAIL_EMBED_VIDEO

    def _embeds_thumbnail(self, job: DownloadJob) -> bool:
        return (
            job.media_type
            in {
                DownloadMediaType.VIDEO,
                DownloadMediaType.AUDIO,
            }
            and job.thumbnail_mode
            in {
                ThumbnailMode.EMBED,
                ThumbnailMode.BOTH,
            }
            and self._container_supports_thumbnail(job)
        )

    def _artifact_job(self, job: DownloadJob) -> DownloadJob:
        job.output_dir.mkdir(parents=True, exist_ok=True)
        return job

    def _output_template(self, job: DownloadJob) -> str:
        template = job.output_template.strip() or "%(title)s.%(ext)s"
        template_path = Path(template)
        if "%(ext)" not in template and template_path.suffix == "":
            template = f"{template}.%(ext)s"
            template_path = Path(template)
        if template_path.is_absolute():
            return str(template_path)
        return str(job.output_dir / template)

    def _video_format_selector(self, quality: str, container: str, audio_lang: str = "") -> str:
        normalized_quality = quality.strip().lower()
        height = self._quality_height(normalized_quality)
        ext_filter = self._video_ext_filter(container)
        audio_container_filter = self._compatible_audio_filter(container)

        audio_filter = audio_container_filter
        if audio_lang:
            audio_filter += f"[language={audio_lang}]"

        generic_audio = "bestaudio"
        if audio_lang:
            generic_audio += f"[language={audio_lang}]"

        if normalized_quality == "lowest":
            if ext_filter or audio_filter:
                return (
                    f"worstvideo{ext_filter}+{generic_audio}{audio_container_filter}/"
                    f"worstvideo{ext_filter}+worstaudio/"
                    f"worst{ext_filter}/worst"
                )
            return "worstvideo+worstaudio/worst"

        if height is None:
            if not audio_lang:
                if ext_filter:
                    return (
                        f"{self._VP9_OPUS_FORMAT_CHAIN}/"
                        f"bestvideo{ext_filter}+bestaudio{audio_container_filter}/"
                        f"bestvideo{ext_filter}+bestaudio/"
                        f"best{ext_filter}/best"
                    )
                return f"{self._VP9_OPUS_FORMAT_CHAIN}/bestvideo+bestaudio"
            if audio_lang:
                if ext_filter:
                    return (
                        f"bestvideo{ext_filter}+bestaudio{audio_filter}/"
                        f"bestvideo{ext_filter}+bestaudio/"
                        f"best{ext_filter}/best"
                    )
                return f"bv*+ba[language={audio_lang}]/bv*+ba/b"
            else:
                if ext_filter:
                    return (
                        f"bestvideo{ext_filter}+bestaudio{audio_container_filter}/"
                        f"bestvideo{ext_filter}+bestaudio/"
                        f"best{ext_filter}/best"
                    )
                return "bv*+ba/b"

        vp9_selector = self._vp9_selector_for_height(height, audio_lang)
        if ext_filter:
            prefix = f"{vp9_selector}/" if vp9_selector else ""
            return (
                f"{prefix}"
                f"bestvideo[height<={height}]{ext_filter}+bestaudio{audio_filter}/"
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]{ext_filter}/best[height<={height}]"
            )

        if audio_lang:
            prefix = f"{vp9_selector}/" if vp9_selector else ""
            return (
                f"{prefix}"
                f"bv*[height<={height}]+ba[language={audio_lang}]/"
                f"bv*[height<={height}]+ba/b[height<={height}]"
            )
        prefix = f"{vp9_selector}/" if vp9_selector else ""
        return f"{prefix}bv*[height<={height}]+ba/b[height<={height}]"

    def _vp9_selector_for_height(self, height: int, audio_lang: str = "") -> str:
        formats = [
            video_id
            for max_height, video_id in self._VP9_HEIGHT_FORMATS.items()
            if max_height <= height
        ]
        if not formats:
            return ""
        audio = self._VP9_OPUS_AUDIO
        if audio_lang:
            return "/".join(f"{video_id}+bestaudio[language={audio_lang}]" for video_id in formats)
        return "/".join(f"{video_id}+{audio}" for video_id in formats)

    def _audio_format_selector(self, audio_format: str, stream_id: str = "") -> str:
        # A concrete source stream (picked in the wizard from real yt-dlp
        # formats) always wins; fall back to heuristics if it disappears.
        if stream_id:
            return f"{stream_id}/bestaudio/best"
        if audio_format == "original":
            return "bestaudio/best"
        if audio_format == "m4a":
            return "bestaudio[ext=m4a]/bestaudio/best"
        if audio_format == "opus":
            return "bestaudio[acodec^=opus]/bestaudio[ext=webm]/bestaudio/best"
        return "bestaudio/best"

    def _progress_hook(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
    ) -> Any:
        def hook(state: dict[str, Any]) -> None:
            self._raise_if_cancelled(job)
            progress = self._download_progress(job, state)
            if progress is not None:
                self._emit_progress(progress_callback, progress)

        return hook

    def _download_progress(
        self,
        job: DownloadJob,
        state: dict[str, Any],
    ) -> DownloadProgress | None:
        status = self._text(state.get("status"))
        if status == "downloading":
            downloaded = self._int_or_none(state.get("downloaded_bytes")) or 0
            total = self._int_or_none(state.get("total_bytes") or state.get("total_bytes_estimate"))
            percent = self._percent(downloaded, total)
            stage = self._download_stage(job, state)
            return DownloadProgress(
                job_id=job.job_id,
                stage=stage,
                percent=percent,
                speed=self._speed_text(state.get("speed")),
                eta=self._eta_text(state.get("eta")),
                bytes_downloaded=downloaded,
                total_bytes=total,
                message=stage_label(stage),
            )
        if status == "finished":
            return DownloadProgress(
                job_id=job.job_id,
                stage=DownloadStage.CLEANING,
                message=stage_label(DownloadStage.CLEANING),
            )
        if status == "error":
            return DownloadProgress(
                job_id=job.job_id,
                stage=DownloadStage.FAILED,
                error="yt-dlp reported a download error.",
            )
        return None

    def _download_stage(self, job: DownloadJob, state: dict[str, Any]) -> DownloadStage:
        info = state.get("info_dict")
        if isinstance(info, dict):
            video_codec = self._text(info.get("vcodec"))
            audio_codec = self._text(info.get("acodec"))
            has_video = video_codec not in {"", "none"}
            has_audio = audio_codec not in {"", "none"}
            if has_video and not has_audio:
                return DownloadStage.DOWNLOADING_VIDEO
            if has_audio and not has_video:
                return DownloadStage.DOWNLOADING_AUDIO
            if has_audio and has_video:
                return DownloadStage.DOWNLOADING_MEDIA

        filename = self._text(state.get("filename"))
        suffix = Path(filename).suffix.lower()
        if suffix in {".m4a", ".mp3", ".opus", ".aac", ".flac", ".wav"} or job.is_audio:
            return DownloadStage.DOWNLOADING_AUDIO
        if suffix in {".mp4", ".webm", ".mkv"}:
            return DownloadStage.DOWNLOADING_VIDEO
        return DownloadStage.DOWNLOADING_MEDIA

    def _emit_stage(
        self,
        progress_callback: ProgressCallback | None,
        job: DownloadJob,
        stage: DownloadStage,
    ) -> None:
        self._emit_progress(
            progress_callback,
            DownloadProgress(
                job_id=job.job_id,
                stage=stage,
                message=stage_label(stage),
            ),
        )

    def _emit_progress(
        self,
        progress_callback: ProgressCallback | None,
        progress: DownloadProgress,
    ) -> None:
        if progress_callback is not None:
            progress_callback(progress)

    def _download_result(
        self,
        job: DownloadJob,
        url: str,
        info: typing.Any,
        media_type: str,
        subtitle_failures: dict[str, str] | None = None,
    ) -> DownloadResult:
        sidecar_files = self._sidecar_files(job)
        files = (
            sidecar_files
            if media_type in {'subtitles', 'thumbnail'} and sidecar_files
            else self._downloaded_files(info)
        )
        return DownloadResult(
            job_id=job.job_id,
            url=url,
            status=DownloadResultStatus.COMPLETED,
            output_dir=job.output_dir,
            files=files,
            media_type=media_type,
            format_id=self._text(info.get('format_id')),
            title=self._text(info.get('title')),
            message=stage_label(DownloadStage.COMPLETED),
            metadata=self._result_metadata(info),
            subtitles_failed=subtitle_failures or {},
        )

    def _sidecar_files(self, job: DownloadJob) -> list[Path]:
        template_name = Path(job.output_template).name
        prefix = template_name.split('%(', 1)[0].rstrip('.')
        patterns = [f'{prefix}*'] if prefix else ['*']
        files: list[Path] = []
        seen: set[Path] = set()
        for pattern in patterns:
            for path in job.output_dir.glob(pattern):
                if not path.is_file():
                    continue
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    files.append(resolved)
        return sorted(files, key=lambda item: item.name)

    def _cleanup_after_cancellation(self, job: DownloadJob) -> None:
        template_name = Path(job.output_template).name
        prefix = template_name.split("%(", 1)[0].rstrip(".")
        if not prefix:
            return

        files = [path for path in job.output_dir.glob(f"{prefix}*") if path.is_file()]
        final_outputs = [
            path
            for path in files
            if path.suffix.lower()
            in {".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus", ".flac", ".wav"}
            and not path.name.endswith(".part")
            and not re.search(r"\.f\d+\.", path.name)
        ]
        if not final_outputs:
            return

        for path in files:
            if path.name.endswith(".part"):
                continue
            if re.search(r"\.f\d+\.", path.name):
                try:
                    path.unlink()
                except OSError:
                    pass

    def _result_metadata(self, info: typing.Any) -> dict[str, str]:
        streams = self._result_streams(info)
        video_item = next(
            (item for item in streams if self._text(item.get("vcodec")) not in {"", "none"}),
            info,
        )
        audio_item = next(
            (item for item in streams if self._text(item.get("acodec")) not in {"", "none"}),
            info,
        )

        values = {
            "title": self._text(info.get("title")),
            "channel": self._text(info.get("channel") or info.get("uploader")),
            "resolution": self._resolution(video_item),
            "format": self._text(info.get("ext") or info.get("container")),
            "video_codec": self._text(video_item.get("vcodec")),
            "video_bitrate": self._bitrate_text(video_item.get("vbr") or video_item.get("tbr")),
            "fps": self._fps_text(video_item.get("fps")),
            "hdr": self._result_hdr(video_item),
            "audio_codec": self._text(audio_item.get("acodec")),
            "audio_bitrate": self._bitrate_text(audio_item.get("abr") or audio_item.get("tbr")),
            "audio_language": self._text(audio_item.get("language") or info.get("language")),
            "duration": self._text(info.get("duration_string")),
            "subtitle_languages": self._result_subtitle_languages(info),
            "chapter_count": self._result_chapter_count(info),
        }
        return {key: value for key, value in values.items() if value and value != "none"}

    def _result_streams(self, info: typing.Any) -> list[dict[str, Any]]:
        """Per-stream dicts for the actually-downloaded formats, best source first.

        ``requested_formats`` holds the individual video/audio streams that were
        merged; it is the most accurate source for codec/bitrate/HDR details.
        Falls back to ``requested_downloads`` (single muxed item) then ``info``.
        """
        for key in ("requested_formats", "requested_downloads"):
            value = info.get(key)
            if isinstance(value, list):
                items = [item for item in value if isinstance(item, dict)]
                if items:
                    return items
        return [info]

    def _result_hdr(self, item: dict[str, Any]) -> str:
        dynamic_range = self._dynamic_range(item)
        return dynamic_range if dynamic_range and dynamic_range.upper() != "SDR" else ""

    def _result_subtitle_languages(self, info: typing.Any) -> str:
        requested = info.get("requested_subtitles")
        if not isinstance(requested, dict):
            return ""
        languages = sorted(str(lang) for lang in requested if lang)
        return ", ".join(languages)

    def _result_chapter_count(self, info: typing.Any) -> str:
        chapters = info.get("chapters")
        if isinstance(chapters, list) and chapters:
            return str(len(chapters))
        return ""

    def _bitrate_text(self, value: object) -> str:
        rate = self._float_or_none(value)
        if rate is None or rate <= 0:
            return ""
        return f"{round(rate)} kbps"

    def _fps_text(self, value: object) -> str:
        fps = self._float_or_none(value)
        if fps is None or fps <= 0:
            return ""
        return f"{round(fps)} fps"

    def _raise_if_cancelled(self, job: DownloadJob) -> None:
        if job.status == JobStatus.CANCELLED:
            raise _DownloadCancelled()

    def _normalized_video_container(self, value: str) -> str:
        container = value.strip().lower()
        if container in {"mp4", "mkv", "webm"}:
            return container
        return "mp4"

    def _normalized_audio_format(self, value: str) -> str:
        audio_format = value.strip().lower()
        if audio_format in {"original", "mp3", "m4a", "flac", "wav", "opus", "aac"}:
            return audio_format
        return "mp3"

    def _quality_height(self, quality: str) -> int | None:
        if quality in {"best", "highest"}:
            return None
        # "1920x1080" (WxH from the analyzer) → 1080
        if "x" in quality:
            _, _, height_part = quality.partition("x")
            try:
                return int(height_part.strip())
            except ValueError:
                return None
        if quality.endswith("p"):
            quality = quality[:-1]
        try:
            return int(quality)
        except ValueError:
            return None

    def _video_ext_filter(self, container: str) -> str:
        if container in {"mp4", "webm"}:
            return f"[ext={container}]"
        return ""

    def _compatible_audio_filter(self, container: str) -> str:
        if container == "mp4":
            return "[ext=m4a]"
        if container == "webm":
            return "[ext=webm]"
        return ""

    def _postprocessor_hook(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
    ) -> Any:
        def hook(state: dict[str, Any]) -> None:
            self._raise_if_cancelled(job)
            progress = self._postprocessor_progress(job, state)
            if progress is not None:
                self._emit_progress(progress_callback, progress)

        return hook

    def _postprocessor_progress(
        self,
        job: DownloadJob,
        state: dict[str, Any],
    ) -> DownloadProgress | None:
        status = self._text(state.get("status"))
        postprocessor = self._text(state.get("postprocessor"))
        if not status:
            return None

        stage = self._postprocessor_stage(postprocessor)
        return DownloadProgress(
            job_id=job.job_id,
            stage=stage,
            percent=100.0,
            message=stage_label(stage),
        )

    def _postprocessor_stage(self, postprocessor: str) -> DownloadStage:
        normalized = postprocessor.lower()
        if "merger" in normalized:
            return DownloadStage.MERGING
        if "metadata" in normalized:
            return DownloadStage.EMBEDDING_METADATA
        if "thumbnail" in normalized:
            return DownloadStage.EMBEDDING_THUMBNAIL
        if "subtitle" in normalized:
            return DownloadStage.PROCESSING_SUBTITLES
        if "extractaudio" in normalized:
            return DownloadStage.DOWNLOADING_AUDIO
        return DownloadStage.CLEANING

    def _audio_quality(self, value: str) -> str:
        quality = value.strip().lower()
        if quality.endswith("k"):
            quality = quality[:-1]
        return quality if quality.isdigit() else "192"

    def _downloaded_files(self, info: typing.Any) -> list[Path]:
        files: list[Path] = []
        seen: set[Path] = set()

        candidates: list[object] = [
            info.get("filepath"),
            info.get("_filename"),
            info.get("filename"),
        ]
        requested_downloads = info.get("requested_downloads")
        if isinstance(requested_downloads, list):
            for item in requested_downloads:
                if not isinstance(item, dict):
                    continue
                candidates.extend(
                    [
                        item.get("filepath"),
                        item.get("_filename"),
                        item.get("filename"),
                    ]
                )

        for candidate in candidates:
            text = self._text(candidate)
            if not text:
                continue
            path = Path(text).expanduser()
            try:
                path = path.resolve()
            except OSError:
                pass
            if path not in seen:
                seen.add(path)
                files.append(path)

        existing = [path for path in files if path.exists()]
        return existing or files

    def _percent(self, downloaded: int, total: int | None) -> float:
        if total is None or total <= 0:
            return 0.0
        return max(0.0, min(100.0, (downloaded / total) * 100))

    def _speed_text(self, value: object) -> str:
        speed = self._float_or_none(value)
        if speed is None:
            return ""
        amount = speed
        for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
            if amount < 1024:
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} TB/s"

    def _eta_text(self, value: object) -> str:
        seconds = self._int_or_none(value)
        if seconds is None:
            return ""
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _get_metadata(self, url: str) -> tuple[str, dict[str, Any]]:
        normalized_url = url.strip()
        if not is_youtube_url(normalized_url):
            raise UnsupportedURLError(f"Not a recognized YouTube URL: {url!r}")

        cached = self._metadata_cache.get(normalized_url)
        if cached is not None:
            return normalized_url, cached

        try:
            with YoutubeDL(typing.cast(typing.Any, self._metadata_options())) as ydl:
                raw_info = ydl.extract_info(normalized_url, download=False)
                info = ydl.sanitize_info(raw_info)
        except Exception as exc:
            raise AnalysisError(f"YouTube metadata analysis failed: {exc}") from None

        if not isinstance(info, dict):
            raise AnalysisError("YouTube metadata analysis returned an invalid response.")

        self._remember_metadata(normalized_url, info)
        return normalized_url, info

    def _remember_metadata(self, url: str, info: typing.Any) -> None:
        if self._metadata_cache_size <= 0:
            return
        if url in self._metadata_cache:
            self._metadata_cache.pop(url)
        elif len(self._metadata_cache) >= self._metadata_cache_size:
            oldest_url = next(iter(self._metadata_cache))
            self._metadata_cache.pop(oldest_url)
        self._metadata_cache[url] = info

    def _normalize_metadata(self, url: str, info: typing.Any) -> YouTubeMetadata:
        video_formats, audio_formats = self._normalize_formats(info.get("formats"))
        thumbnails = self._normalize_thumbnails(info.get("thumbnails"))
        media_type = self._detect_media_type(url, info)

        return YouTubeMetadata(
            url=self._text(info.get("webpage_url")) or url,
            title=self._text(info.get("title")),
            uploader=self._text(info.get("uploader") or info.get("channel")),
            channel_id=self._text(info.get("channel_id") or info.get("uploader_id")),
            video_id=self._text(info.get("id")) if media_type != ProviderMediaType.PLAYLIST else "",
            duration=self._int_or_none(info.get("duration")),
            description=self._text(info.get("description")),
            upload_date=self._text(info.get("upload_date")),
            view_count=self._int_or_none(info.get("view_count")),
            like_count=self._int_or_none(info.get("like_count")),
            thumbnail_url=self._text(info.get("thumbnail")),
            thumbnails=thumbnails,
            media_type=media_type,
            playlist_title=self._playlist_title(info, media_type),
            playlist_count=self._playlist_count(info, media_type),
            subtitle_languages=self._language_keys(info.get("subtitles")),
            automatic_subtitle_languages=self._language_keys(info.get("automatic_captions")),
            video_formats=video_formats,
            audio_formats=audio_formats,
            containers=self._containers(video_formats, audio_formats),
            resolutions=self._resolutions(video_formats),
            fps_values=self._fps_values(video_formats),
            hdr_formats=self._hdr_formats(video_formats),
        )

    def _normalize_thumbnails(self, value: object) -> list[ThumbnailMetadata]:
        if not isinstance(value, list):
            return []

        thumbnails: list[ThumbnailMetadata] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            thumbnail_url = self._text(item.get("url"))
            if not thumbnail_url:
                continue
            thumbnails.append(
                ThumbnailMetadata(
                    url=thumbnail_url,
                    width=self._int_or_none(item.get("width")),
                    height=self._int_or_none(item.get("height")),
                    resolution=self._text(item.get("resolution")),
                    thumbnail_id=self._text(item.get("id")),
                )
            )
        return thumbnails

    def _normalize_formats(
        self,
        value: object,
    ) -> tuple[list[VideoFormatMetadata], list[AudioFormatMetadata]]:
        if not isinstance(value, list):
            return [], []

        video_formats: list[VideoFormatMetadata] = []
        audio_formats: list[AudioFormatMetadata] = []

        for item in value:
            if not isinstance(item, dict):
                continue

            video_codec = self._text(item.get("vcodec"))
            audio_codec = self._text(item.get("acodec"))
            has_video = video_codec not in {"", "none"}
            has_audio = audio_codec not in {"", "none"}

            if has_video:
                video_formats.append(
                    VideoFormatMetadata(
                        format_id=self._text(item.get("format_id")),
                        extension=self._text(item.get("ext")),
                        container=self._container(item),
                        resolution=self._resolution(item),
                        fps=self._float_or_none(item.get("fps")),
                        video_codec=video_codec,
                        filesize=self._filesize(item),
                        dynamic_range=self._dynamic_range(item),
                    )
                )

            if has_audio and not has_video:
                audio_formats.append(
                    AudioFormatMetadata(
                        format_id=self._text(item.get("format_id")),
                        extension=self._text(item.get("ext")),
                        container=self._container(item),
                        audio_codec=audio_codec,
                        bitrate=self._float_or_none(item.get("abr") or item.get("tbr")),
                        filesize=self._filesize(item),
                    )
                )

        return video_formats, audio_formats

    def _normalize_capability_formats(
        self, value: object
    ) -> tuple[list[VideoFormatOption], list[AudioFormatOption]]:
        if not isinstance(value, list):
            return [], []

        video_formats: list[VideoFormatOption] = []
        audio_formats: list[AudioFormatOption] = []

        seen_video: set[tuple[object, ...]] = set()
        seen_audio: set[tuple[object, ...]] = set()

        for item in value:
            if not isinstance(item, dict):
                continue

            video_codec = self._text(item.get("vcodec"))
            audio_codec = self._text(item.get("acodec"))
            has_video = video_codec not in {"", "none"}
            has_audio = audio_codec not in {"", "none"}

            if has_video:
                video = VideoFormatOption(
                    format_id=self._text(item.get("format_id")),
                    resolution=self._resolution(item),
                    width=self._int_or_none(item.get("width")),
                    height=self._int_or_none(item.get("height")),
                    fps=self._float_or_none(item.get("fps")),
                    codec=video_codec,
                    container=self._container(item),
                    filesize=self._filesize(item),
                    is_hdr=self._is_hdr(item),
                    bitrate=self._float_or_none(item.get("vbr") or item.get("tbr")),
                    dynamic_range=self._capability_dynamic_range(item),
                    note=self._capability_note(item),
                )
                key = self._video_dedupe_key(video)
                if key not in seen_video:
                    seen_video.add(key)
                    video_formats.append(video)

            if has_audio and not has_video:
                audio = AudioFormatOption(
                    format_id=self._text(item.get("format_id")),
                    codec=audio_codec,
                    bitrate=self._float_or_none(item.get("abr") or item.get("tbr")),
                    sample_rate=self._int_or_none(item.get("asr")),
                    channels=self._int_or_none(item.get("audio_channels")),
                    filesize=self._filesize(item),
                    container=self._container(item),
                )
                key = self._audio_dedupe_key(audio)
                if key not in seen_audio:
                    seen_audio.add(key)
                    audio_formats.append(audio)

        return (
            sorted(video_formats, key=self._video_sort_key, reverse=True),
            sorted(audio_formats, key=self._audio_sort_key, reverse=True),
        )

    def _normalize_subtitle_languages(self, value: object) -> list[SubtitleLanguageOption]:
        if not isinstance(value, dict):
            return []

        languages: list[SubtitleLanguageOption] = []
        for language_code, tracks in value.items():
            if not language_code or "tlang=" in language_code:
                continue

            track_list = tracks if isinstance(tracks, list) else []
            formats = self._subtitle_formats(track_list)
            languages.append(
                SubtitleLanguageOption(
                    language_code=str(language_code),
                    language_name=self._subtitle_language_name(str(language_code), track_list),
                    formats=formats,
                )
            )

        return sorted(languages, key=lambda item: item.language_code)

    def _normalize_thumbnail_options(self, value: object) -> list[ThumbnailOption]:
        if not isinstance(value, list):
            return []

        thumbnails: list[ThumbnailOption] = []
        seen: set[str] = set()

        for item in value:
            if not isinstance(item, dict):
                continue
            thumbnail_url = self._text(item.get("url"))
            if not thumbnail_url or thumbnail_url in seen:
                continue
            seen.add(thumbnail_url)
            width = self._int_or_none(item.get("width"))
            height = self._int_or_none(item.get("height"))
            thumbnails.append(
                ThumbnailOption(
                    resolution=self._thumbnail_resolution(item, width, height),
                    width=width,
                    height=height,
                    preference=self._int_or_none(item.get("preference")),
                    url=thumbnail_url,
                )
            )

        return thumbnails

    def _detect_media_type(self, url: str, info: typing.Any) -> ProviderMediaType:
        if info.get("_type") == "playlist" or isinstance(info.get("entries"), list):
            return ProviderMediaType.PLAYLIST
        webpage_url = self._text(info.get("webpage_url"))
        if "/shorts/" in url or "/shorts/" in webpage_url:
            return ProviderMediaType.SHORTS
        return ProviderMediaType.VIDEO

    def _playlist_title(self, info: typing.Any, media_type: ProviderMediaType) -> str:
        if media_type != ProviderMediaType.PLAYLIST:
            return ""
        return self._text(info.get("playlist_title") or info.get("title"))

    def _playlist_count(
        self,
        info: typing.Any,
        media_type: ProviderMediaType,
    ) -> int | None:
        if media_type != ProviderMediaType.PLAYLIST:
            return None
        explicit_count = self._int_or_none(info.get("playlist_count") or info.get("n_entries"))
        if explicit_count is not None:
            return explicit_count
        entries = info.get("entries")
        if isinstance(entries, list):
            return len(entries)
        return None

    def _language_keys(self, value: object) -> list[str]:
        if not isinstance(value, dict):
            return []
        return sorted(str(language) for language in value if language)

    def _containers(
        self,
        video_formats: list[VideoFormatMetadata],
        audio_formats: list[AudioFormatMetadata],
    ) -> list[str]:
        values = [fmt.container for fmt in video_formats] + [fmt.container for fmt in audio_formats]
        return self._unique_text(values)

    def _resolutions(self, video_formats: list[VideoFormatMetadata]) -> list[str]:
        return self._unique_text(fmt.resolution for fmt in video_formats if fmt.resolution)

    def _fps_values(self, video_formats: list[VideoFormatMetadata]) -> list[float]:
        return sorted({fmt.fps for fmt in video_formats if fmt.fps is not None})

    def _hdr_formats(self, video_formats: list[VideoFormatMetadata]) -> list[str]:
        return self._unique_text(fmt.dynamic_range for fmt in video_formats if fmt.dynamic_range)

    def _container(self, item: dict[str, Any]) -> str:
        return self._text(item.get("container") or item.get("ext"))

    def _resolution(self, item: dict[str, Any]) -> str:
        resolution = self._text(item.get("resolution"))
        if resolution and resolution != "audio only":
            return resolution

        height = self._int_or_none(item.get("height"))
        width = self._int_or_none(item.get("width"))
        if width and height:
            return f"{width}x{height}"
        if height:
            return f"{height}p"
        return ""

    def _dynamic_range(self, item: dict[str, Any]) -> str:
        dynamic_range = self._text(item.get("dynamic_range"))
        if dynamic_range and dynamic_range.upper() != "SDR":
            return dynamic_range

        format_note = self._text(item.get("format_note"))
        upper_note = format_note.upper()
        for marker in ("HDR", "HLG", "DOLBY VISION", "DV"):
            if marker in upper_note:
                return marker
        return ""

    def _filesize(self, item: dict[str, Any]) -> int | None:
        return self._int_or_none(item.get("filesize") or item.get("filesize_approx"))

    def _capability_dynamic_range(self, item: dict[str, Any]) -> str:
        dynamic_range = self._text(item.get("dynamic_range"))
        if dynamic_range:
            return dynamic_range
        return self._dynamic_range(item)

    def _is_hdr(self, item: dict[str, Any]) -> bool:
        dynamic_range = self._capability_dynamic_range(item).upper()
        if dynamic_range and dynamic_range != "SDR":
            return True

        note = self._text(item.get("format_note")).upper()
        return any(marker in note for marker in ("HDR", "HLG", "DOLBY VISION", "DV"))

    def _capability_note(self, item: dict[str, Any]) -> str:
        notes = [
            self._text(item.get("format_note")),
            self._text(item.get("format")),
        ]
        codec = self._text(item.get("vcodec")).lower()
        if codec.startswith("av01") and not any("av1" in note.lower() for note in notes):
            notes.append("AV1")
        if self._is_hdr(item) and not any("hdr" in note.lower() for note in notes):
            notes.append(self._capability_dynamic_range(item))
        return " | ".join(dict.fromkeys(note for note in notes if note))

    def _subtitle_formats(self, tracks: list[object]) -> list[str]:
        formats: set[str] = set()
        for track in tracks:
            if not isinstance(track, dict):
                continue
            extension = self._text(track.get("ext"))
            if extension:
                formats.add(extension)
        return sorted(formats)

    def _subtitle_language_name(self, language_code: str, tracks: list[object]) -> str:
        for track in tracks:
            if not isinstance(track, dict):
                continue
            name = self._text(track.get("name"))
            if name:
                return name
        return _LANGUAGE_NAMES.get(language_code.lower(), language_code)

    def _thumbnail_resolution(
        self,
        item: dict[str, Any],
        width: int | None,
        height: int | None,
    ) -> str:
        resolution = self._text(item.get("resolution"))
        if resolution:
            return resolution
        if width and height:
            return f"{width}x{height}"
        return ""

    def _video_dedupe_key(self, video: VideoFormatOption) -> tuple[object, ...]:
        if video.format_id:
            return (video.format_id,)
        return (
            video.resolution,
            video.width,
            video.height,
            video.fps,
            video.codec,
            video.container,
            video.dynamic_range,
            video.bitrate,
        )

    def _audio_dedupe_key(self, audio: AudioFormatOption) -> tuple[object, ...]:
        if audio.format_id:
            return (audio.format_id,)
        return (
            audio.codec,
            audio.bitrate,
            audio.sample_rate,
            audio.channels,
            audio.container,
        )

    def _video_sort_key(self, video: VideoFormatOption) -> tuple[object, ...]:
        return (
            video.height or 0,
            video.width or 0,
            1 if video.is_hdr else 0,
            video.fps or 0.0,
            video.bitrate or 0.0,
            video.filesize or 0,
        )

    def _audio_sort_key(self, audio: AudioFormatOption) -> tuple[object, ...]:
        return (
            audio.bitrate or 0.0,
            audio.sample_rate or 0,
            audio.channels or 0,
            audio.filesize or 0,
        )

    def _thumbnail_sort_key(self, thumbnail: ThumbnailOption) -> tuple[int, int, int, int]:
        width = thumbnail.width or 0
        height = thumbnail.height or 0
        return (
            width * height,
            thumbnail.preference or 0,
            width,
            height,
        )

    def _unique_text(self, values: Iterable[object]) -> list[str]:
        return sorted({self._text(value) for value in values if self._text(value)})

    def _text(self, value: object) -> str:
        if value is None:
            return ""
        return str(value)

    def _int_or_none(self, value: object) -> int | None:
        try:
            if value is None or value == "":
                return None
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                return int(value)
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _float_or_none(self, value: object) -> float | None:
        try:
            if value is None or value == "":
                return None
            if isinstance(value, int | float):
                return float(value)
            return float(str(value))
        except (TypeError, ValueError):
            return None


_LANGUAGE_NAMES = {
    "ar": "Arabic",
    "de": "German",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
}
