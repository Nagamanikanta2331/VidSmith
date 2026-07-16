"""YouTube provider stub for the downloader architecture."""

from __future__ import annotations

import logging
import re
import time
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
    MetadataMode,
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
from mediaforge.utils.environment import environment_summary, js_runtimes_option
from mediaforge.utils.exceptions import AnalysisError, DownloadError, UnsupportedURLError
from mediaforge.utils.validators import is_youtube_url


class _DownloadCancelled(Exception):
    """Internal signal used to stop yt-dlp from a progress hook."""


_logger = logging.getLogger("mediaforge.provider.youtube")

# Hard cap for the per-subtitle-request throttle. yt-dlp sleeps this long
# before EVERY subtitle track (fetched before media), so total pre-download
# wait is delay × track count — 15s × 4 tracks is already a full minute.
_MAX_SUBTITLE_SLEEP = 15


class _SubtitleLogger:
    """Silent yt-dlp logger that records subtitle-download failures.

    yt-dlp reports a failed subtitle language as a *warning* (never fatal), e.g.
    ``Unable to download video subtitles for 'ar': HTTP Error 429``.  We capture
    those so the summary can list which languages failed and why, without
    un-suppressing the rest of yt-dlp's chatter.

    Everything yt-dlp says is also forwarded to the ``mediaforge`` debug log,
    so with Debug Logging enabled the full diagnostic stream (extraction steps,
    retries, JS-runtime output) lands in mediaforge.log instead of vanishing.
    """

    _SUB_WARNING = re.compile(
        r"[Uu]nable to download.*?subtitles?(?: for)? ['\"]?([A-Za-z][\w-]*)['\"]?\s*[:\-]?\s*(.*)"
    )

    def __init__(self) -> None:
        self.subtitle_failures: dict[str, str] = {}
        # Last error line yt-dlp reported — surfaced when extract_info()
        # returns None instead of raising (ignoreerrors swallows the raise).
        self.last_error: str = ""
        self.logger = logging.getLogger("mediaforge.subtitle")
        self._ytdlp_logger = logging.getLogger("mediaforge.ytdlp")

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
        self._ytdlp_logger.debug(message)
        if message and not message.startswith("[debug]"):
            self._record(message)

    def info(self, message: str) -> None:
        self._ytdlp_logger.info(message)
        self._record(message)

    def warning(self, message: str) -> None:
        self._ytdlp_logger.warning(message)
        self._record(message)

    def error(self, message: str) -> None:
        self._ytdlp_logger.error(message)
        if message.strip():
            self.last_error = message.strip()
        self._record(message)


def _short_error(message: str) -> str:
    """First line of a yt-dlp error, trimmed to fit a one-line progress label."""
    first_line = message.strip().splitlines()[0] if message.strip() else "Unknown error"
    return first_line if len(first_line) <= 80 else first_line[:77] + "..."


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
        # job_id → (current stage, monotonic start time) for stage timing logs.
        self._stage_started: dict[str, tuple[DownloadStage, float]] = {}
        # Guarded because building the summary shells out to ffmpeg/node;
        # cached in environment_summary(), so repeated provider rebuilds (e.g.
        # after a settings change) don't re-probe binaries.
        if _logger.isEnabledFor(logging.DEBUG):
            _logger.debug("Environment: %s", environment_summary())

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
        run_options: dict[str, Any] = {**options, "logger": subtitle_logger, "no_warnings": False}

        # One-line record of what we actually ask yt-dlp for — the exact data
        # needed to reproduce a MediaForge download with the official CLI.
        # Cookies are logged even while always None so a diff against a manual
        # `--cookies-from-browser` CLI run makes the gap obvious.
        _logger.debug(
            "yt-dlp run: url=%s format=%r js_runtimes=%r subtitleslangs=%r merge=%r "
            "cookiesfrombrowser=%r cookiefile=%r",
            normalized_url,
            run_options.get("format"),
            run_options.get("js_runtimes"),
            run_options.get("subtitleslangs"),
            run_options.get("merge_output_format"),
            run_options.get("cookiesfrombrowser"),
            run_options.get("cookiefile"),
        )

        attempt = 1
        while attempt <= attempts:
            try:
                self._raise_if_cancelled(job)
                self._emit_stage(progress_callback, job, DownloadStage.EXTRACTING)
                # A configured subtitle throttle makes yt-dlp sleep BEFORE each
                # subtitle request (subtitles come before media), so a large
                # delay looks exactly like a hang unless the label says so.
                sleep_s = int(run_options.get("sleep_interval_subtitles", 0) or 0)
                sub_langs: list[str] = list(run_options.get("subtitleslangs") or [])
                select_message = stage_label(DownloadStage.SELECTING)
                if sleep_s > 0 and sub_langs and not options.get("skip_download"):
                    select_message += (
                        f" — subtitle throttle {sleep_s}s × {len(sub_langs)} track(s), "
                        f"expect ~{sleep_s * len(sub_langs)}s before media starts"
                    )
                self._emit_progress(
                    progress_callback,
                    DownloadProgress(
                        job_id=job.job_id,
                        stage=DownloadStage.SELECTING,
                        message=select_message,
                    ),
                )
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

                sub_err = re.search(r"Unable to download video subtitles for '([^']+)'", last_error)
                if sub_err:
                    failed_lang = sub_err.group(1)
                    if attempt >= attempts:
                        _logger.warning(
                            "Skipping failing subtitle language '%s' after %d attempts.",
                            failed_lang,
                            attempts,
                        )
                        langs = list(run_options.get("subtitleslangs", []))
                        if failed_lang in langs:
                            langs.remove(failed_lang)
                        if langs:
                            run_options["subtitleslangs"] = langs
                        else:
                            run_options["subtitleslangs"] = []
                            run_options["writesubtitles"] = False
                            run_options["writeautomaticsub"] = False
                        attempts += 1
                    else:
                        run_options["sleep_interval_subtitles"] = (
                            int(run_options.get("sleep_interval_subtitles", 0) or 0) + 5
                        )

                _logger.warning(
                    "Attempt %d/%d failed for %s: %s", attempt, attempts, normalized_url, last_error
                )
                if attempt >= attempts:
                    raise DownloadError(
                        f"YouTube {media_type} download failed after {attempts} attempts: {last_error}"
                    ) from None
                # Tell the user we are retrying and why, instead of leaving the
                # spinner frozen on the previous stage for the whole retry cycle.
                self._emit_progress(
                    progress_callback,
                    DownloadProgress(
                        job_id=job.job_id,
                        stage=DownloadStage.RETRYING,
                        message=f"⚠ Retrying ({attempt + 1}/{attempts}): {_short_error(last_error)}",
                    ),
                )
                attempt += 1
                continue

            if not isinstance(info, dict):
                # With ignoreerrors set, yt-dlp reports fatal failures through
                # its logger and returns None instead of raising — surface the
                # real reason and retry like any other failure.
                last_error = (
                    subtitle_logger.last_error or "YouTube returned no data (no error reported)."
                )

                sub_err = re.search(r"Unable to download video subtitles for '([^']+)'", last_error)
                if sub_err:
                    failed_lang = sub_err.group(1)
                    if attempt >= attempts:
                        _logger.warning(
                            "Skipping failing subtitle language '%s' after %d attempts.",
                            failed_lang,
                            attempts,
                        )
                        langs = list(run_options.get("subtitleslangs", []))
                        if failed_lang in langs:
                            langs.remove(failed_lang)
                        if langs:
                            run_options["subtitleslangs"] = langs
                        else:
                            run_options["subtitleslangs"] = []
                            run_options["writesubtitles"] = False
                            run_options["writeautomaticsub"] = False
                        attempts += 1
                    else:
                        run_options["sleep_interval_subtitles"] = (
                            int(run_options.get("sleep_interval_subtitles", 0) or 0) + 5
                        )

                _logger.warning(
                    "Attempt %d/%d returned no info for %s: %s",
                    attempt,
                    attempts,
                    normalized_url,
                    last_error,
                )
                if attempt >= attempts:
                    raise DownloadError(
                        f"YouTube {media_type} download failed after {attempts} attempts: {last_error}"
                    )
                self._emit_progress(
                    progress_callback,
                    DownloadProgress(
                        job_id=job.job_id,
                        stage=DownloadStage.RETRYING,
                        message=f"⚠ Retrying ({attempt + 1}/{attempts}): {_short_error(last_error)}",
                    ),
                )
                attempt += 1
                continue

            self._remember_metadata(normalized_url, info)
            # Rate-limited subtitle tracks are warnings (never fatal), so the
            # media download "succeeds" while languages are missing. Recover
            # them now with an escalating-delay retry ladder before building
            # the result, so the summary and cleanup see the recovered files.
            extra_subtitle_files = self._retry_rate_limited_subtitles(
                job, normalized_url, run_options, subtitle_logger, progress_callback
            )
            if extra_subtitle_files and media_type == "video":
                media_file = next(
                    (
                        f
                        for f in self._downloaded_files(info)
                        if f.suffix.lower()
                        not in {
                            ".vtt",
                            ".srt",
                            ".ass",
                            ".lrc",
                            ".ttml",
                            ".jpg",
                            ".jpeg",
                            ".png",
                            ".webp",
                            ".json",
                        }
                    ),
                    None,
                )
                if media_file is not None:
                    self._emit_progress(
                        progress_callback,
                        DownloadProgress(
                            job_id=job.job_id,
                            stage=DownloadStage.PROCESSING_SUBTITLES,
                            message="Embedding recovered subtitles",
                        ),
                    )
                    self._embed_recovered_subtitles(job, media_file, extra_subtitle_files)
            result = self._download_result(
                job,
                normalized_url,
                info,
                media_type,
                subtitle_logger.subtitle_failures,
                extra_files=extra_subtitle_files,
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

    # Escalating per-retry delay for rate-limited subtitle tracks: +5s per
    # attempt (5, 10, 15, 20, 25s), up to 5 tries per language, then skip.
    _SUBTITLE_RETRY_STEP = 5
    _SUBTITLE_RETRY_MAX = 5

    def _retry_rate_limited_subtitles(
        self,
        job: DownloadJob,
        url: str,
        run_options: dict[str, Any],
        subtitle_logger: _SubtitleLogger,
        progress_callback: ProgressCallback | None,
    ) -> list[Path]:
        """Re-fetch subtitle tracks that YouTube rate-limited (HTTP 429).

        The main download treats a failed subtitle as a warning and moves on,
        so this runs afterwards: one subtitle-only yt-dlp pass per retry
        round, waiting 5s more before each round (5, 10, … 25s), until every
        language succeeded or 5 rounds passed. Languages that recover are removed
        from ``subtitle_logger.subtitle_failures`` so the summary reports
        them as downloaded; the returned sidecar paths are appended to the
        download result for validation/cleanup.
        """
        failed = {
            lang: reason
            for lang, reason in subtitle_logger.subtitle_failures.items()
            if "429" in reason or "Rate Limited" in reason
        }
        if not failed:
            return []

        recovered_files: list[Path] = []
        remaining = list(failed)

        for attempt in range(1, self._SUBTITLE_RETRY_MAX + 1):
            if not remaining:
                break
            # The media file is already on disk; a cancel during the retry
            # ladder just stops the subtitle recovery, never the download.
            if job.status == JobStatus.CANCELLED:
                return recovered_files
            delay = self._SUBTITLE_RETRY_STEP * attempt
            self._emit_progress(
                progress_callback,
                DownloadProgress(
                    job_id=job.job_id,
                    stage=DownloadStage.RETRYING,
                    message=(
                        f"⚠ Subtitles rate-limited ({', '.join(remaining)}) — "
                        f"waiting {delay}s, retry {attempt}/{self._SUBTITLE_RETRY_MAX}"
                    ),
                ),
            )
            for _ in range(delay):
                if job.status == JobStatus.CANCELLED:
                    return recovered_files
                time.sleep(1)

            retry_logger = _SubtitleLogger()
            retry_options: dict[str, Any] = {
                **run_options,
                "logger": retry_logger,
                "no_warnings": False,
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": list(remaining),
                "embedsubtitles": False,
                "embedthumbnail": False,
                "writethumbnail": False,
                "addmetadata": False,
                "postprocessors": [],
            }
            try:
                with YoutubeDL(typing.cast(typing.Any, retry_options)) as ydl:
                    raw_info = ydl.extract_info(url, download=True)
                    info = ydl.sanitize_info(raw_info)
            except _DownloadCancelled:
                return recovered_files
            except Exception as exc:
                _logger.warning("Subtitle retry %d failed entirely: %s", attempt, exc)
                continue

            still_failed = set(retry_logger.subtitle_failures)
            newly_recovered = [lang for lang in remaining if lang not in still_failed]
            if newly_recovered and isinstance(info, dict):
                recovered_files.extend(
                    f
                    for f in self._downloaded_files(info)
                    if f.suffix.lower() in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}
                )
                for lang in newly_recovered:
                    subtitle_logger.subtitle_failures.pop(lang, None)
                    _logger.info("Recovered rate-limited subtitle '%s' on retry %d.", lang, attempt)
            remaining = [lang for lang in remaining if lang in still_failed]

        for lang in remaining:
            _logger.warning(
                "Skipping subtitle '%s' after %d rate-limit retries.",
                lang,
                self._SUBTITLE_RETRY_MAX,
            )
        return recovered_files

    # Subtitle codec ffmpeg must write per container when muxing recovered
    # sidecars into the finished file.
    _SUBTITLE_MUX_CODECS = {
        ".mp4": "mov_text",
        ".m4v": "mov_text",
        ".mov": "mov_text",
        ".mkv": "srt",
        ".webm": "webvtt",
    }

    def _embed_recovered_subtitles(
        self,
        job: DownloadJob,
        media_file: Path,
        subtitle_files: list[Path],
    ) -> None:
        """Mux retry-recovered sidecar subtitles into the finished container.

        Tracks recovered by the rate-limit retry ladder arrive after yt-dlp's
        postprocessing, so FFmpegEmbedSubtitle never saw them and they would
        stay behind as stray .vtt files. Remux them in with a stream copy
        (no re-encode, takes seconds). Strictly best-effort: on any failure
        the original file is untouched and the sidecar is kept — exactly the
        pre-existing behaviour.
        """
        from mediaforge.subtitle import ISO_639_2

        if job.media_type != DownloadMediaType.VIDEO or not self._embeds_subtitles(job):
            return
        sub_codec = self._SUBTITLE_MUX_CODECS.get(media_file.suffix.lower())
        if sub_codec is None or not media_file.exists():
            return
        subs = [f for f in subtitle_files if f.exists() and f.suffix.lower() in {".vtt", ".srt"}]
        if not subs:
            return

        ffmpeg = which("ffmpeg")
        if not ffmpeg:
            # yt-dlp's ffmpeg_location may be the binary itself or its folder.
            location = self._ffmpeg_location_option().get("ffmpeg_location", "")
            candidate = Path(location) if location else None
            if candidate is not None and candidate.is_file():
                ffmpeg = str(candidate)
            elif candidate is not None and candidate.is_dir():
                for name in ("ffmpeg.exe", "ffmpeg"):
                    if (candidate / name).exists():
                        ffmpeg = str(candidate / name)
                        break
        ffprobe = which("ffprobe")
        if not ffmpeg or not ffprobe:
            _logger.info("ffmpeg/ffprobe unavailable — recovered subtitles stay as sidecars.")
            return

        import json as _json
        import os
        import subprocess

        try:
            probe = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-select_streams",
                    "s",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "json",
                    str(media_file),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            existing_subs = len(_json.loads(probe.stdout).get("streams", []))
        except Exception as exc:
            _logger.warning("Could not probe %s before subtitle mux: %s", media_file.name, exc)
            return

        tmp_file = media_file.with_name(f"{media_file.stem}.submux{media_file.suffix}")
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(media_file)]
        for sub in subs:
            cmd += ["-i", str(sub)]
        cmd += ["-map", "0"]
        for i in range(len(subs)):
            cmd += ["-map", f"{i + 1}:0"]
        # -strict -2: opus-in-mp4 (Best Download's usual audio) is still gated
        # as experimental by ffmpeg's mp4 muxer, even for stream copies.
        cmd += ["-c", "copy", "-c:s", sub_codec, "-strict", "-2"]
        for i, sub in enumerate(subs):
            parts = sub.suffixes
            base = parts[-2].strip(".").split("-")[0].lower() if len(parts) >= 2 else ""
            iso3 = ISO_639_2.get(base)
            if iso3:
                cmd += [f"-metadata:s:s:{existing_subs + i}", f"language={iso3}"]
        cmd += [str(tmp_file)]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if (
                proc.returncode != 0
                or not tmp_file.exists()
                or tmp_file.stat().st_size < media_file.stat().st_size * 0.9
            ):
                _logger.warning(
                    "Muxing recovered subtitles into %s failed (rc=%s): %s",
                    media_file.name,
                    proc.returncode,
                    (proc.stderr or "").strip()[:500],
                )
                tmp_file.unlink(missing_ok=True)
                return
            os.replace(tmp_file, media_file)
            _logger.info(
                "Embedded %d recovered subtitle track(s) into %s.", len(subs), media_file.name
            )
        except Exception as exc:
            _logger.warning("Subtitle mux into %s failed: %s", media_file.name, exc)
            tmp_file.unlink(missing_ok=True)

    def _build_download_options(
        self,
        job: DownloadJob,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, Any]:
        options = self._base_download_options(job, progress_callback)

        # Artifact-only downloads (subtitles/thumbnail only)
        if job.media_type in (
            DownloadMediaType.TRANSCRIPT,
            DownloadMediaType.SUBTITLE,
            DownloadMediaType.THUMBNAIL,
        ):
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

            # Adaptive delay for HTTP 429 errors during subtitle-only downloads:
            # 5s more per retry (5, 10, 15, 20, 25s), up to 5 tries.
            if job.media_type == DownloadMediaType.SUBTITLE:
                options["retries"] = 5
                options["retry_sleep"] = {"http": "linear=5:25:5"}

            # Convert the saved thumbnail to the user's chosen image format
            # (jpg/png/webp). Empty means "keep whatever YouTube served".
            if job.media_type == DownloadMediaType.THUMBNAIL and job.thumbnail_format:
                options["postprocessors"] = [
                    {
                        "key": "FFmpegThumbnailsConvertor",
                        "format": job.thumbnail_format,
                        "when": "before_dl",
                    }
                ]

            if job.media_type == DownloadMediaType.SUBTITLE and getattr(
                job, "transcript_format", ""  # type: ignore
            ):
                options["subtitlesformat"] = "vtt"  # Ensure we download vtt for the postprocessor

            return options

        # Audio Download
        if job.media_type == DownloadMediaType.AUDIO:
            audio_format = self._normalized_audio_format(job.audio_format)
            options["format"] = self._audio_format_selector(
                audio_format, getattr(job, "audio_stream_id", "")
            )
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
            "embedsubtitles": self._embeds_subtitles(job),
            "writethumbnail": self._writes_thumbnail(job),
            "embedthumbnail": self._embeds_thumbnail(job),
            "addmetadata": job.metadata_mode == MetadataMode.EMBED,
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
            "file_access_retries": 3,
            "continuedl": True,
            "buffersize": 1024 * 1024,
            "concurrent_fragment_downloads": 5,
            "socket_timeout": 20,
            "http_chunk_size": 10 * 1024 * 1024,
            "progress_delta": 0.2,
            # Subtitle/postprocessing failures must not abort the media
            # download. NOTE: yt-dlp only downgrades a failed subtitle track
            # to a warning when ignoreerrors is exactly True — with
            # "only_download" it RAISES (YoutubeDL._write_subtitles), killing
            # the whole video over one 429. Real media failures still surface:
            # yt-dlp reports them and returns None, which _run_download turns
            # into a retry/DownloadError, and the executor validates the final
            # files either way.
            "ignoreerrors": True,
        }

        # Throttling each subtitle request keeps YouTube from rate-limiting.
        # Clamped: the sleep runs once per requested track BEFORE media starts,
        # so large values multiply into minutes of apparent hang.
        subtitle_sleep = int(self.config.get("subtitle_sleep_interval", 0))
        if subtitle_sleep > _MAX_SUBTITLE_SLEEP:
            _logger.warning(
                "subtitle_sleep_interval %ss exceeds the %ss cap; clamping.",
                subtitle_sleep,
                _MAX_SUBTITLE_SLEEP,
            )
            subtitle_sleep = _MAX_SUBTITLE_SLEEP
        if subtitle_sleep > 0:
            defaults["sleep_interval_subtitles"] = subtitle_sleep

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

        # Subtitle embedding is handled by yt-dlp's FFmpegEmbedSubtitle, which
        # muxes the written sidecar tracks into the final container.
        if self._embeds_subtitles(job):
            postprocessors.append(
                {
                    "key": "FFmpegEmbedSubtitle",
                    "already_have_subtitle": True,
                }
            )

        # Metadata + chapters are embedded by yt-dlp's FFmpegMetadata.
        if job.metadata_mode == MetadataMode.EMBED:
            postprocessors.append(
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                    "add_chapters": True,
                    "add_infojson": False,
                }
            )

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
        """Exact subtitle codes to request from yt-dlp."""
        return [lang.strip() for lang in job.subtitle_languages if lang.strip()]

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
        self._log_stage_transition(progress)
        if progress_callback is not None:
            progress_callback(progress)

    def _log_stage_transition(self, progress: DownloadProgress) -> None:
        """Debug-log how long each stage took, keyed by job.

        Produces a per-download timeline in mediaforge.log (extract 0.8s,
        subtitles 3.2s, ...) that shows where time is actually spent.
        """
        if not _logger.isEnabledFor(logging.DEBUG):
            return
        from time import monotonic

        previous = self._stage_started.get(progress.job_id)
        now = monotonic()
        if previous is not None and previous[0] != progress.stage:
            _logger.debug(
                "Job %s: stage %s took %.1fs, now %s",
                progress.job_id,
                previous[0].value,
                now - previous[1],
                progress.stage.value,
            )
        if previous is None or previous[0] != progress.stage:
            self._stage_started[progress.job_id] = (progress.stage, now)
        if progress.stage in (
            DownloadStage.COMPLETED,
            DownloadStage.FAILED,
            DownloadStage.CANCELLED,
        ):
            self._stage_started.pop(progress.job_id, None)

    def _download_result(
        self,
        job: DownloadJob,
        url: str,
        info: typing.Any,
        media_type: str,
        subtitle_failures: dict[str, str] | None = None,
        extra_files: list[Path] | None = None,
    ) -> DownloadResult:
        files = self._downloaded_files(info)
        for path in extra_files or []:
            if path not in files:
                files.append(path)
        # Artifact-only downloads must not report media files: with
        # skip_download yt-dlp still computes the video filename, and if a
        # previous run left that exact file in the folder it would be picked
        # up as the "primary output" (wrong name/format/size in the summary).
        if media_type == "thumbnail":
            files = [f for f in files if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}]
        elif media_type == "subtitles":
            files = [
                f for f in files if f.suffix.lower() in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}
            ]
        return DownloadResult(
            job_id=job.job_id,
            url=url,
            status=DownloadResultStatus.COMPLETED,
            output_dir=job.output_dir,
            files=files,
            media_type=media_type,
            format_id=self._text(info.get("format_id")),
            title=self._text(info.get("title")),
            message=stage_label(DownloadStage.COMPLETED),
            metadata=self._result_metadata(info),
            subtitles_failed=subtitle_failures or {},
        )

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

        thumbnails = info.get("thumbnails")
        if isinstance(thumbnails, list):
            for item in thumbnails:
                if not isinstance(item, dict):
                    continue
                candidates.extend(
                    [
                        item.get("filepath"),
                        item.get("_filename"),
                        item.get("filename"),
                    ]
                )

        requested_subtitles = info.get("requested_subtitles")
        if isinstance(requested_subtitles, dict):
            for item in requested_subtitles.values():
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
