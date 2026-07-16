"""
Glue layer: translates WizardState + AnalysisResult into a concrete job,
dispatches it through the correct engine, and renders progress via Rich.

The UI (wizard, dispatcher) never knows about yt-dlp, FFmpeg, or engine internals.
The engines never know about Rich or the console.
"""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter

from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from vidsmith.cli.summary import build_summary, render_summary
from vidsmith.cli.wizard.base import WizardState
from vidsmith.downloader.job import (
    DownloadJob,
    DownloadMediaType,
    MetadataMode,
    SubtitleMode,
    ThumbnailMode,
)
from vidsmith.downloader.manager import DownloadManager
from vidsmith.downloader.progress import (
    DownloadProgress,
    DownloadStage,
    ProgressCallback,
    stage_label,
)
from vidsmith.downloader.validator import DownloadValidationResult, validate_download
from vidsmith.downloader.validators.models import ValidationErrorCode
from vidsmith.models.media import AnalysisResult
from vidsmith.playlist.models import PlaylistJob, PlaylistSelectionMode
from vidsmith.providers.results import DownloadResult
from vidsmith.providers.youtube import YouTubeProvider
from vidsmith.subtitle import (
    SUPPORTED_SUBTITLE_LANGUAGES,
    SubtitleSelection,
    resolve_subtitle_selection,
)
from vidsmith.utils.console import console
from vidsmith.utils.exceptions import DownloadError

# ── provider singleton (created once, reused for the session) ─────────────────

_provider: YouTubeProvider | None = None
_environment_warned = False


def _warn_environment_once() -> None:
    """Show friendly one-time warnings for missing optional tooling.

    Keeps yt-dlp's own raw warnings suppressed while still telling the user how
    to close quality gaps (impersonation, cover-art atoms, JS runtime).
    """
    global _environment_warned
    if _environment_warned:
        return
    _environment_warned = True

    from vidsmith.utils.environment import environment_warnings

    messages = environment_warnings()
    if not messages:
        return
    body = "\n".join(f"[yellow]•[/] {message}" for message in messages)
    console.print()
    console.print(
        Panel(
            Text.from_markup(body),
            title="[warning] Optional tools for full yt-dlp parity [/]",
            border_style="yellow",
            padding=(0, 2),
        )
    )


def _get_provider() -> YouTubeProvider:
    global _provider
    if _provider is None:
        from vidsmith.settings.store import current_settings

        s = current_settings()
        config = {
            "subtitle_sleep_interval": s.subtitle_delay_seconds,
            "ffmpeg_location": s.ffmpeg_path_override or None,
            "node_path_override": s.node_path_override,
        }
        _provider = YouTubeProvider(config=config)
    return _provider


def _reset_provider() -> None:
    """Drop the cached provider so it rebuilds with fresh settings next use."""
    global _provider
    _provider = None


def _get_manager() -> DownloadManager:
    return DownloadManager.create(_get_provider())


# ── public entry points ───────────────────────────────────────────────────────


def execute_video(state: WizardState, result: AnalysisResult) -> None:
    """Build a video DownloadJob from wizard state and run it."""
    job = _video_job(state, result)
    _run_download(job, "video", analysis=result)

    # Execute the user-requested cleanup command after custom download
    import subprocess

    cmd = 'del /q "*.jpg" "*.webp" "*.vtt" "*.srt" "*.ass" "*.info.json" "*.description" "*.part" "*.ytdl"'
    try:
        subprocess.run(cmd, shell=True, cwd=str(job.output_dir))
    except Exception:
        pass


def execute_audio(state: WizardState, result: AnalysisResult) -> None:
    """Build an audio DownloadJob from wizard state and run it."""
    job = _audio_job(state, result)
    _run_download(job, "audio", analysis=result)


def execute_settings(state: WizardState) -> None:
    """Persist settings collected by the settings wizard.

    Settings are media-independent, so this takes no AnalysisResult. Maps the
    WizardState keys onto AppSettings, writes them to disk, and resets the
    provider singleton so the next download picks up the new config.
    """
    from vidsmith.settings import AppSettings
    from vidsmith.settings.store import save_settings, set_current

    s = AppSettings()
    for field_name in (
        "default_output_directory",
        "default_container",
        "default_quality",
        "default_audio_format",
        "default_audio_quality",
        "cleanup_enabled",
        "keep_temp_files",
        "node_path_override",
        "ffmpeg_path_override",
        "max_concurrency",
        "debug_logging",
    ):
        value = state.get(field_name)
        if value is not None:
            setattr(s, field_name, value)

    delay_mode = state.get("subtitle_delay_mode")
    if delay_mode is not None:
        if delay_mode == "custom":
            custom_val = state.get("subtitle_delay_custom")
            if custom_val is not None:
                s.subtitle_delay_seconds = int(custom_val)
        else:
            s.subtitle_delay_seconds = int(delay_mode)

    save_settings(s)
    set_current(s)
    _reset_provider()


def execute_playlist(state: WizardState, result: AnalysisResult) -> None:
    """Build a PlaylistJob from wizard state and run each item through the engine."""
    from vidsmith.playlist.engine import PlaylistEngine
    from vidsmith.playlist.models import PlaylistItem

    output_dir = _resolve_dir(state.get("output_dir", "~/Downloads"))
    media_type_key = state.get("media_type", "video")
    quality = state.get("quality", "best")
    item_selection = state.get("item_selection", "all")
    item_range = state.get("item_range", "")

    dl_media_type = (
        DownloadMediaType.AUDIO if media_type_key == "audio" else DownloadMediaType.VIDEO
    )

    selection_mode, selected_indices, range_start, range_end = _parse_playlist_selection(
        item_selection, item_range, result
    )

    items = (
        [
            PlaylistItem(url=item.url, index=i + 1, title=item.title)
            for i, item in enumerate(result.items)
        ]
        if result.items
        else []
    )

    # Video items get the wizard's subtitle selection, ordered by the
    # supported-language policy. English is a mandatory fallback — it is
    # requested even when deselected, so every item gets at least the auto
    # English track merged when one exists (availability is unknown from
    # flat analysis, and missing languages are non-fatal). Audio items keep
    # subtitles off.
    template = DownloadJob(
        url=result.url,
        media_type=dl_media_type,
        output_dir=output_dir,
        quality=quality,
    )
    if dl_media_type == DownloadMediaType.VIDEO:
        chosen = set(state.get("subtitle_langs") or []) | {"en"}
        langs = [lang for lang in SUPPORTED_SUBTITLE_LANGUAGES if lang in chosen]
        template.subtitle_mode = SubtitleMode.BOTH
        template.subtitle_languages = langs
        template.subtitle_requested_languages = langs

    playlist_job = PlaylistJob(
        url=result.url,
        output_dir=output_dir,
        items=items,
        download_template=template,
        selection_mode=selection_mode,
        selected_indices=selected_indices,
        range_start=range_start,
        range_end=range_end,
        skip_unavailable=True,
        continue_after_failures=True,
    )

    manager = _get_manager()
    engine = PlaylistEngine(download_manager=manager, provider=_get_provider())

    with _progress_spinner(f"Queuing {result.title}") as progress:
        task = progress.add_task("Submitting playlist…", total=None)
        pl_result = engine.submit(playlist_job)
        progress.update(task, description=f"Queued {len(pl_result.queued_job_ids)} items")

    if pl_result.errors:
        _show_error("Playlist Errors", "\n".join(pl_result.errors[:5]))

    total = len(pl_result.queued_job_ids)
    concurrency = int(state.get("concurrency", 1) or 1)
    _run_queued(manager, total, result.title, concurrency=concurrency)


def execute_transcript(state: WizardState, result: AnalysisResult) -> None:
    """Download subtitle track and convert it to the requested transcript format."""
    from vidsmith.downloader.job import DownloadJob, DownloadMediaType, SubtitleMode
    from vidsmith.transcript.engine import TranscriptEngine
    from vidsmith.transcript.models import (
        TimestampMode,
        TranscriptJob,
        TranscriptOutputFormat,
    )

    while True:
        output_dir = _resolve_dir(state.get("output_dir", "~/Downloads"))
        language = state.get("language", "en")
        output_format_key = state.get("output_format", "txt")
        include_timestamps = state.get("include_timestamps", False)

        fmt_map = {
            "txt": TranscriptOutputFormat.TEXT,
            "md": TranscriptOutputFormat.MARKDOWN,
            "json": TranscriptOutputFormat.JSON,
            "srt": TranscriptOutputFormat.SRT,
            "vtt": TranscriptOutputFormat.VTT,
        }
        output_format = fmt_map.get(output_format_key, TranscriptOutputFormat.TEXT)
        ts_mode = TimestampMode.START if include_timestamps else TimestampMode.NONE

        safe_title = _safe_filename(result.title or "transcript")
        output_path = output_dir / f"{safe_title}.{output_format_key}"
        output_dir.mkdir(parents=True, exist_ok=True)

        provider = _get_provider()

        selection = _resolve_job_subtitles(result, [language])
        actual_codes = selection.codes if selection.codes else [language]

        dl_job = DownloadJob(
            url=result.url,
            media_type=DownloadMediaType.TRANSCRIPT,
            output_dir=output_dir,
            subtitle_mode=SubtitleMode.BOTH,
            subtitle_languages=actual_codes,
        )

        with _progress_spinner(f"Downloading subtitles ({language})") as progress:
            task = progress.add_task("Fetching subtitle track...", total=None)

            def _on_progress(p: DownloadProgress) -> None:
                pass

            try:
                dl_result = provider.download_transcript(dl_job, _on_progress)
            except Exception as exc:
                _show_error("Transcript Download Failed", str(exc))
                return

            validation = validate_download(dl_job, dl_result)

            if (
                not validation.subtitle.success
                or language not in validation.subtitle.sidecar_languages
            ):
                reason = validation.subtitle.failed_languages.get(language, "Unavailable")
                if "429" in reason or "Rate Limited" in reason:
                    _show_error(
                        "Transcript temporarily unavailable.",
                        "YouTube is rate limiting subtitle requests.\nPlease try again later.",
                    )
                    return
                else:
                    _show_error(
                        "Transcription Not Available",
                        f"The requested language ({language}) is not available.\nPlease select another language.",
                    )
                    from vidsmith.cli.wizard.wizards.transcript import build_transcript_wizard

                    wizard = build_transcript_wizard(result)
                    new_state = wizard.run(initial={"__media__": result})
                    if new_state is None:
                        return
                    state = new_state
                    continue

            progress.update(task, description="Subtitle downloaded")

        # The validate_download should have verified the sidecar is present.
        # Find the sidecar in dl_result.files
        subtitle_file = next(
            (
                f
                for f in dl_result.files
                if f.suffix.lower() in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}
            ),
            None,
        )
        if not subtitle_file:
            _show_error("Subtitle Not Found", "No subtitle file generated.")
            return

        transcript_validation = None

        with _progress_spinner("Converting transcript") as progress:
            task = progress.add_task("Converting...", total=None)
            try:
                engine = TranscriptEngine()
                transcript_job = TranscriptJob(
                    input_path=subtitle_file,
                    output_path=output_path,
                    output_format=output_format,
                    timestamp_mode=ts_mode,
                    title=result.title,
                    language=language,
                )
                transcript_validation = engine.convert(transcript_job)
                progress.update(task, description="Conversion complete")

                # Clean up intermediate files. Use the exact paths yt-dlp reported
                # (dl_result.files) — yt-dlp sanitizes titles differently than
                # _safe_filename (e.g. "|" vs "_"), so a glob on safe_title can
                # miss the real sidecar. Keep the glob as a fallback for stray
                # partials that match our sanitization.
                candidates = [f for f in dl_result.files if f is not None]
                candidates.extend(output_dir.glob(f"{safe_title}*"))
                for f in candidates:
                    if (
                        f.is_file()
                        and f.resolve() != transcript_validation.output_path.resolve()
                        and f.suffix.lower() in {".vtt", ".srt", ".part", ".temp", ".tmp", ".ytdl"}
                    ):
                        try:
                            f.unlink()
                        except OSError:
                            pass
            except Exception as exc:
                _show_error("Transcript Conversion Failed", str(exc))
                return

        # Final summary panel
        _show_success(
            "Transcript Completed",
            "\n".join(
                [
                    f"[bold cyan]Caption Source:[/bold cyan] {subtitle_file.name}",
                    f"[bold cyan]Language:[/bold cyan] {language}",
                    f"[bold cyan]Output Format:[/bold cyan] {output_format_key.upper()}",
                    f"[bold cyan]Output File:[/bold cyan] {output_path.name}",
                    "[bold cyan]Conversion Status:[/bold cyan] Success",
                ]
            ),
        )

        from rich.prompt import Prompt

        Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")
        return


def execute_best_download(state: WizardState, result: AnalysisResult) -> None:
    """
    Run the recommended video preset through the shared download engine.
    """
    output_dir = _prompt_download_location()
    if output_dir is None:
        return

    job = _best_video_job(result, output_dir)
    _run_download(job, "best video", success_title="Best Download Complete", analysis=result)


def execute_best_playlist_download(state: WizardState, result: AnalysisResult) -> None:
    """Apply the recommended video preset to every playlist item.

    Items download in parallel (the "Parallel Downloads" setting, default 3):
    each worker gets its own ``YoutubeDL`` instance, so wall-clock time drops
    close to 1/N without changing per-item behavior.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from vidsmith.settings.store import current_settings

    output_dir = _prompt_download_location()
    if output_dir is None:
        return

    items = result.items or []
    if not items:
        _show_error("Empty Playlist", "No items were found in this playlist.")
        return

    _warn_environment_once()
    completed = 0
    failed: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    provider = _get_provider()
    workers = max(1, min(current_settings().max_concurrency, len(items)))

    def _download_item(index: int, item_url: str, title: str) -> tuple[str, str, str]:
        job = _best_video_job(result, output_dir, url=item_url)
        job.output_template = f"{index:03d} - %(title)s.%(ext)s"
        try:
            dl_res = provider.download(job)
            validation = _finalize_download(job, dl_res, strict=False)
            if not validation.success:
                return ("warning", title, validation.error_message or "Validation warning")
            return ("ok", title, "")
        except Exception as exc:
            return ("error", title, str(exc))

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as bar:
        task_id = bar.add_task(
            f"Best Download: {result.title} ({workers} at a time)",
            total=len(items),
        )

        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_download_item, index, item.url, item.title or f"Item {index}")
                for index, item in enumerate(items, 1)
            ]
            for future in as_completed(futures):
                kind, title, msg = future.result()
                if kind == "error":
                    failed.append((title, msg))
                else:
                    completed += 1
                    if kind == "warning":
                        warnings.append((title, msg))
                done += 1
                bar.update(task_id, completed=done)

    lines: list[str] = [
        f"[dim]Output directory:[/] {output_dir}",
        "[dim]Container:[/] MP4 (yt-dlp parity)",
        f"[dim]Completed:[/] {completed}/{len(items)}",
        f"[dim]Failed:[/] {len(failed)}",
    ]
    if failed:
        lines.append("")
        lines.append("[bold red]Failures:[/]")
        for title, err in failed[:5]:
            lines.append(f"  [dim]-[/] {title}: [red]{_format_item_error(err)}[/]")
    if warnings:
        lines.append("")
        lines.append("[bold yellow]Warnings (media saved, embed check failed):[/]")
        for title, warn in warnings[:5]:
            lines.append(f"  [dim]-[/] {title}: [yellow]{_format_item_error(warn)}[/]")

    title = (
        "Playlist Best Download Complete"
        if not failed
        else f"Playlist Complete ({len(failed)} failed)"
    )
    _show_success(title, "\n".join(lines))


# ── job builders ──────────────────────────────────────────────────────────────


# Best Download prefers VP9 because Windows Explorer correctly displays
# embedded thumbnails for VP9 files. Highest VP9+Opus pairs first
# (313=2160p, 308=1440p, 303=1080p, 302=720p, 251=Opus); the generic
# bestvideo+bestaudio fallback is used ONLY when no preferred format is
# available. Streams are merged into MP4 as-is — never transcoded.
def _resolve_job_subtitles(
    result: AnalysisResult | None,
    requested: list[str] | None = None,
) -> SubtitleSelection:
    """Resolve the supported-language policy against an analysis result.

    Manual tracks win, auto-generated fill the gaps, missing languages are
    skipped silently (they surface as "⚠ unavailable" in the summary, never
    as an error). Translated (``tlang=``) tracks were already dropped by the
    analyzer, so they can never be requested here.
    """
    if result is None:
        return SubtitleSelection()
    return resolve_subtitle_selection(
        result.subtitle_languages or [],
        result.automatic_subtitle_languages or [],
        requested,
    )


def _blind_subtitle_selection() -> SubtitleSelection:
    """Supported-language selection for items with no per-item caption data.

    Playlist analysis is flat (``extract_flat``), so per-item subtitle
    availability is unknown. Request the full supported set and let yt-dlp
    download whatever exists — with ``ignoreerrors=True`` unavailable tracks
    are warnings, and the subtitle validator reports them as "unavailable"
    without failing the item.
    """
    langs = list(SUPPORTED_SUBTITLE_LANGUAGES)
    return SubtitleSelection(codes=langs, requested=langs)


def _video_job(state: WizardState, result: AnalysisResult) -> DownloadJob:
    output_dir = _resolve_dir(state.get("output_dir", "~/Downloads"))
    quality = state.get("quality", "best")
    video_format = state.get("format", "mp4")
    thumbnail_mode_str = state.get("thumbnail_mode", "embed")
    subtitle_langs = state.get("subtitle_langs", [])
    audio_lang = state.get("audio_lang", "")

    thumb_map = {
        "embed": ThumbnailMode.EMBED,
        "save": ThumbnailMode.SAVE,
        "both": ThumbnailMode.BOTH,
        "none": ThumbnailMode.NONE,
    }

    selection = (
        _resolve_job_subtitles(result, subtitle_langs) if subtitle_langs else SubtitleSelection()
    )
    sub_mode = SubtitleMode.BOTH if selection.codes else SubtitleMode.NONE

    return DownloadJob(
        url=result.url,
        media_type=DownloadMediaType.VIDEO,
        output_dir=output_dir,
        quality=quality,
        video_format=video_format,
        subtitle_mode=sub_mode,
        subtitle_languages=selection.codes,
        subtitle_requested_languages=selection.requested,
        subtitle_auto_languages=selection.auto_languages,
        audio_language=audio_lang,
        thumbnail_mode=thumb_map.get(thumbnail_mode_str, ThumbnailMode.EMBED),
    )


def _best_video_job(
    result: AnalysisResult,
    output_dir: Path,
    *,
    url: str | None = None,
) -> DownloadJob:
    # Preferred subtitle languages (en/hi/te/ta): manual over auto, silent
    # skip when a language is unavailable. Playlist items are analyzed flat
    # (no per-item subtitle data), so the full supported set is requested
    # blindly — yt-dlp downloads whatever exists, missing tracks surface as
    # "⚠ unavailable" warnings, never an error.
    selection = _resolve_job_subtitles(result) if url is None else _blind_subtitle_selection()
    sub_mode = SubtitleMode.BOTH if selection.codes else SubtitleMode.NONE

    # MP4 merge with embedded thumbnail, metadata, chapters, and subtitles.
    # Streams are merged without transcoding; the format selector applies an
    # [ext=...] filter for MP4 device compatibility.
    return DownloadJob(
        url=url or result.url,
        media_type=DownloadMediaType.VIDEO,
        output_dir=output_dir,
        quality="best",
        video_format="mp4",
        subtitle_mode=sub_mode,
        subtitle_languages=selection.codes,
        subtitle_requested_languages=selection.requested,
        subtitle_auto_languages=selection.auto_languages,
        thumbnail_mode=ThumbnailMode.EMBED,
        metadata_mode=MetadataMode.EMBED,
    )


def _audio_job(state: WizardState, result: AnalysisResult) -> DownloadJob:
    output_dir = _resolve_dir(state.get("output_dir", "~/Downloads"))
    audio_format = state.get("audio_format", "original")
    audio_stream_id = state.get("audio_stream_id", "")
    embed_thumbnail = bool(state.get("embed_thumbnail", True))
    embed_metadata = bool(state.get("embed_metadata", True))

    # Transcode at the source stream's real bitrate — never invent one.
    # When no specific stream was chosen, fall back to the configured default.
    from vidsmith.settings.store import current_settings

    audio_quality = current_settings().default_audio_quality
    if audio_stream_id:
        for stream in result.audio_streams:
            if stream.format_id == audio_stream_id and stream.bitrate > 0:
                audio_quality = f"{round(stream.bitrate)}k"
                break

    return DownloadJob(
        url=result.url,
        media_type=DownloadMediaType.AUDIO,
        output_dir=output_dir,
        audio_format=audio_format,
        audio_quality=audio_quality,
        audio_stream_id=audio_stream_id,
        thumbnail_mode=ThumbnailMode.EMBED if embed_thumbnail else ThumbnailMode.NONE,
        metadata_mode=MetadataMode.EMBED if embed_metadata else MetadataMode.NONE,
    )


# --- direct artifact actions --------------------------------------------------


def execute_subtitles(state: WizardState, result: AnalysisResult) -> None:
    """Download subtitle files only (supported languages, manual over auto)."""
    output_dir = _resolve_dir(state.get("output_dir", "~/Downloads"))
    languages = state.get("languages", [])
    output_format = state.get("output_format", "vtt")

    if not languages:
        return

    selection = _resolve_job_subtitles(result, languages)
    from vidsmith.transcript.engine import TranscriptEngine
    from vidsmith.transcript.models import (
        TimestampMode,
        TranscriptJob,
        TranscriptOutputFormat,
    )

    fmt_map = {
        "txt": TranscriptOutputFormat.TEXT,
        "md": TranscriptOutputFormat.MARKDOWN,
        "json": TranscriptOutputFormat.JSON,
        "srt": TranscriptOutputFormat.SRT,
        "vtt": TranscriptOutputFormat.VTT,
    }
    engine_format = fmt_map.get(output_format, TranscriptOutputFormat.VTT)

    job = DownloadJob(
        url=result.url,
        media_type=DownloadMediaType.SUBTITLE,
        output_dir=output_dir,
        subtitle_mode=SubtitleMode.BOTH,
        subtitle_languages=selection.codes,
        subtitle_requested_languages=selection.requested,
        subtitle_auto_languages=selection.auto_languages,
        metadata_mode=MetadataMode.NONE,
        thumbnail_mode=ThumbnailMode.NONE,
        transcript_format="vtt",  # Always download vtt, convert later
    )

    provider = _get_provider()

    with _progress_spinner("Downloading subtitles") as progress:
        task = progress.add_task("Fetching subtitle tracks...", total=None)

        def _on_progress(p: DownloadProgress) -> None:
            pass

        try:
            dl_result = provider.download_subtitles(job, _on_progress)
        except Exception as exc:
            _show_error("Subtitle Download Failed", str(exc))
            return

        progress.update(task, description="Subtitles downloaded")

    # If the user wanted vtt or srt, we're done (yt-dlp handled it or we just keep vtt)
    # Wait, yt-dlp might not convert to SRT automatically if we forced vtt.
    # But if we need conversion, we use TranscriptEngine.
    if engine_format != TranscriptOutputFormat.VTT:
        with _progress_spinner("Converting subtitles") as progress:
            task = progress.add_task("Converting format...", total=None)
            engine = TranscriptEngine()

            for file_path in dl_result.files:
                if file_path.suffix.lower() == ".vtt":
                    out_path = file_path.with_suffix(f".{output_format}")

                    # Try to infer language from filename (e.g. video.en.vtt)
                    # This is just for internal tagging in JSON
                    lang_guess = file_path.stem.split(".")[-1] if "." in file_path.stem else "en"

                    t_job = TranscriptJob(
                        input_path=file_path,
                        output_path=out_path,
                        output_format=engine_format,
                        timestamp_mode=(
                            TimestampMode.NONE if output_format == "txt" else TimestampMode.START
                        ),
                        title=result.title,
                        language=lang_guess,
                    )
                    try:
                        engine.convert(t_job)
                        # Optionally delete the original vtt file
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        # Log to standard error/warning stream if logging is configured
                        pass

            progress.update(task, description="Conversion complete")

    _show_success("Subtitles Saved", f"Saved to {output_dir}")


def execute_thumbnail(state: WizardState, result: AnalysisResult) -> None:
    """Download the best thumbnail only, in the user's chosen image format."""
    output_dir = _prompt_download_location()
    if output_dir is None:
        return
    thumbnail_format = _prompt_thumbnail_format()
    if thumbnail_format is None:
        return
    job = DownloadJob(
        url=result.url,
        media_type=DownloadMediaType.THUMBNAIL,
        output_dir=output_dir,
        metadata_mode=MetadataMode.NONE,
        thumbnail_mode=ThumbnailMode.SAVE,
        thumbnail_format=thumbnail_format,
    )
    _run_download(job, "thumbnail", success_title="Thumbnail Saved", analysis=result)


def _prompt_thumbnail_format() -> str | None:
    """Ask which image format to save the thumbnail as. None = cancelled."""
    formats = {"1": "jpg", "2": "png", "3": "webp"}
    console.print()
    console.print("[bold cyan]Thumbnail Format[/]")
    console.print("  1  JPG   [dim](best compatibility)[/]")
    console.print("  2  PNG   [dim](lossless)[/]")
    console.print("  3  WebP  [dim](original YouTube format)[/]")
    choice = Prompt.ask("Choose format", choices=[*formats, "q"], default="1")
    if choice == "q":
        return None
    return formats[choice]


def _format_filesize(size_in_bytes: int) -> str:
    if not size_in_bytes:
        return ""
    val = float(size_in_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if val < 1024.0:
            return f"{val:.2f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{val:.2f} PB"


def _format_upload_date(date_str: str) -> str:
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str


def execute_metadata(state: WizardState, result: AnalysisResult) -> None:
    """Show normalized metadata for the current media."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column(style="white")

    highest_res = result.resolutions[0] if result.resolutions else ""
    available_res = ", ".join(result.resolutions)
    available_containers = ", ".join(result.containers)

    codecs_set = set(result.video_codecs + result.audio_codecs)
    available_codecs = ", ".join(sorted(codecs_set))

    sub_count = len(result.subtitle_languages) + len(result.automatic_subtitle_languages)
    audio_lang_count = len(result.audio_languages)

    rows = [
        ("Title", result.title),
        ("Video ID", result.video_id),
        ("URL", result.url),
        ("Channel", result.uploader),
        ("Upload Date", _format_upload_date(result.upload_date)),
        ("Duration", _media_duration(result.duration)),
        ("Views", f"{result.view_count:,}" if result.view_count else ""),
        ("Highest Resolution", highest_res),
        ("Available Resolutions", available_res),
        ("Available Containers", available_containers),
        ("Available Codecs", available_codecs),
        (
            "Subtitle Count",
            (
                f"{sub_count} ({len(result.subtitle_languages)} manual, {len(result.automatic_subtitle_languages)} auto)"
                if sub_count
                else ""
            ),
        ),
        ("Audio Language Count", str(audio_lang_count) if audio_lang_count else ""),
        ("Estimated File Size", _format_filesize(result.estimated_file_size)),
        ("Thumbnail", result.thumbnail_url),
        ("Items", str(result.item_count) if result.item_count else ""),
    ]
    for label, value in rows:
        if value:
            table.add_row(label, value)

    console.print()
    console.print(
        Panel(
            table,
            title="[bold cyan] Metadata [/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")


# --- download execution -------------------------------------------------------


def _run_download(
    job: DownloadJob,
    media_type: str,
    *,
    success_title: str = "Download Complete",
    analysis: AnalysisResult | None = None,
) -> None:
    """Execute a single download job with one Rich progress task."""
    _warn_environment_once()
    provider = _get_provider()
    dl_result = None
    error: tuple[str, str] | None = None
    started_at = perf_counter()

    if not console.is_terminal:
        try:
            dl_result = _execute_provider_download(provider, job, media_type)
            validation = _finalize_download(job, dl_result)
        except KeyboardInterrupt:
            job.mark_cancelled()
            _show_cancelled()
            return
        except DownloadError as exc:
            _show_error("Download Failed", str(exc))
            return
        except Exception as exc:
            _show_error("Unexpected Error", str(exc))
            return

        summary = build_summary(job, dl_result, validation, perf_counter() - started_at, analysis)
        render_summary(success_title, summary)
        return

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=24),
        TextColumn("[cyan]{task.fields[percent]}"),
        TextColumn("[dim]{task.fields[bytes]}"),
        TextColumn("[green]{task.fields[speed]}"),
        TextColumn("[yellow]{task.fields[eta]}"),
        TimeElapsedColumn(),
        console=console,
        auto_refresh=False,
        expand=True,
    )

    with Live(progress, console=console, refresh_per_second=12, transient=True) as live:
        task_id = progress.add_task(
            f"Preparing {media_type}",
            total=100,
            percent="",
            bytes="",
            speed="",
            eta="",
        )

        def _on_progress(p: DownloadProgress) -> None:
            total, completed, percent = _progress_total_completed(p)
            progress.update(
                task_id,
                total=total,
                completed=completed,
                description=_progress_description(p, media_type),
                percent=percent,
                bytes=_progress_bytes(p),
                speed=p.speed,
                eta=f"ETA {p.eta}" if p.eta else "",
            )
            live.refresh()

        try:
            dl_result = _execute_provider_download(
                provider,
                job,
                media_type,
                progress_callback=_on_progress,
            )

            validation = _finalize_download(job, dl_result)
        except KeyboardInterrupt:
            job.mark_cancelled()
            error = (
                "Download Cancelled",
                "Download cancelled. Temporary .part files were kept for resume.",
            )
        except DownloadError as exc:
            error = ("Download Failed", str(exc))
        except Exception as exc:
            error = ("Unexpected Error", str(exc))

        if error is None:
            progress.update(
                task_id,
                total=100,
                completed=100,
                description=stage_label(DownloadStage.COMPLETED),
                percent="100%",
                bytes="",
                speed="",
                eta="",
            )
        else:
            progress.update(
                task_id,
                total=None,
                completed=0,
                description=error[0],
                percent="",
                bytes="",
                speed="",
                eta="",
            )
        live.refresh()

    if error is not None:
        if error[0] == "Download Cancelled":
            _show_cancelled(error[1])
        else:
            _show_error(error[0], error[1])
        return

    if dl_result is None:
        return

    summary = build_summary(job, dl_result, validation, perf_counter() - started_at, analysis)
    render_summary(success_title, summary)


# Validation codes that mean the media file itself is missing/unusable.
# Anything else (thumbnail/subtitle/metadata embed checks) means the media
# downloaded fine and a post-processing check failed — a warning for
# playlist items, not a failed download.
_FATAL_VALIDATION_CODES = {
    ValidationErrorCode.FILE_MISSING,
    ValidationErrorCode.FILE_EMPTY,
}


def _finalize_download(
    job: DownloadJob,
    dl_result: DownloadResult,
    *,
    strict: bool = True,
) -> DownloadValidationResult:
    """Validate a finished download and clean up temp artifacts on success.

    The single post-download contract shared by every mode: validate the final
    file, raise ``DownloadError`` if it failed, then remove temporary artifacts
    (passing the validation so only successfully-embedded sidecars are deleted).

    With ``strict=False`` (playlist items), validation failures whose media
    file exists (e.g. a thumbnail that didn't embed) do NOT raise — the
    result is returned so the caller can report them as warnings. Cleanup is
    skipped in that case so temporary artifacts stay available for recovery.
    """
    from vidsmith.settings.store import current_settings

    s = current_settings()

    validation = validate_download(job, dl_result)
    if not validation.success:
        if strict or validation.error_code in _FATAL_VALIDATION_CODES:
            raise DownloadError(validation.error_message or "Validation failed.")
        return validation

    from vidsmith.downloader.cleanup import cleanup_job_artifacts

    deleted_files = cleanup_job_artifacts(
        job,
        dl_result.files,
        validation,
        cleanup_enabled=s.cleanup_enabled,
        keep_temp_files=s.keep_temp_files,
    )

    if job.subtitle_requested_languages or job.subtitle_languages:
        import logging

        logger = logging.getLogger("vidsmith.subtitle")

        req = (
            ", ".join(job.subtitle_requested_languages)
            if job.subtitle_requested_languages
            else "all"
        )
        res = ", ".join(job.subtitle_languages) if job.subtitle_languages else "none"

        dl_subs = validation.subtitle.downloaded_languages if validation.subtitle else []
        dl = ", ".join(dl_subs) if dl_subs else "none"

        emb_subs = validation.subtitle.embedded_languages if validation.subtitle else []
        emb = "yes" if emb_subs else "no"

        val = "PASS" if validation.success else "FAIL"

        sub_deleted = [
            f.name for f in deleted_files if f.suffix in {".vtt", ".srt", ".ass", ".lrc", ".ttml"}
        ]
        if not s.cleanup_enabled:
            cln = "disabled"
        elif sub_deleted:
            cln = f"deleted sidecar ({', '.join(sub_deleted)})"
        else:
            cln = "kept sidecar"

        logger.info(
            f"Requested: {req} -> Resolved: {res} -> yt-dlp requested: {res} -> Downloaded: {dl} -> Embedded: {emb} -> Validator: {val} -> Cleanup: {cln}"
        )

    return validation


def _execute_provider_download(
    provider: YouTubeProvider,
    job: DownloadJob,
    media_type: str,
    *,
    progress_callback: ProgressCallback | None = None,
) -> DownloadResult:
    if media_type == "subtitles":
        return provider.download_subtitles(job, progress_callback=progress_callback)
    if media_type == "thumbnail":
        return provider.download_thumbnail(job, progress_callback=progress_callback)
    if job.media_type == DownloadMediaType.AUDIO:
        return provider.download_audio(job, progress_callback=progress_callback)
    return provider.download(job, progress_callback=progress_callback)


# The retry wrapper prefixes every failure with this constant text; in the
# playlist summary it just eats the line budget, hiding the real reason.
_ATTEMPT_PREFIX = re.compile(r"^YouTube \w+ download failed after \d+ attempts:\s*", re.IGNORECASE)


def _format_item_error(msg: str, limit: int = 160) -> str:
    """Compact a per-item failure for the playlist summary panel."""
    text = _ATTEMPT_PREFIX.sub("", msg.strip()).strip()
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text or "Unknown error"


def _run_queued(
    manager: DownloadManager,
    total: int,
    title: str,
    concurrency: int = 1,
) -> None:
    """Drive pending jobs in the manager to completion, showing Rich progress.

    Jobs run through a thread pool sized by *concurrency* (the wizard's
    "Parallel Downloads" answer). Each worker uses its own ``YoutubeDL``
    instance, so parallel items never share yt-dlp state.
    """
    if total == 0:
        _show_error("Nothing Queued", "No items were submitted to the download queue.")
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    from vidsmith.downloader.job import JobStatus as _JS

    provider = _get_provider()
    pending = manager.list_jobs(status_filter=_JS.PENDING)
    workers = max(1, min(concurrency, len(pending))) if pending else 1

    def _download_one(job: DownloadJob) -> tuple[str, str]:
        job.mark_running()
        try:
            if job.media_type == DownloadMediaType.AUDIO:
                dl_res = provider.download_audio(job)
            else:
                dl_res = provider.download(job)

            validation = _finalize_download(job, dl_res, strict=False)

            job.mark_completed()
            if not validation.success:
                return (
                    "warning",
                    _format_item_error(validation.error_message or "Validation warning"),
                )
            return ("ok", "")
        except Exception as exc:
            job.mark_failed(str(exc))
            return ("error", _format_item_error(str(exc)))

    done = 0
    errors: list[str] = []
    warnings: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as bar:
        task_id = bar.add_task(
            f"Downloading {title}… ({workers} at a time)",
            total=total,
        )

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_download_one, job) for job in pending]
            for future in as_completed(futures):
                kind, msg = future.result()
                if kind == "error":
                    errors.append(msg)
                elif kind == "warning":
                    warnings.append(msg)
                done += 1
                bar.update(task_id, completed=done)

    if errors:
        body = "\n".join(errors[:5])
        if warnings:
            body += "\n\n[bold yellow]Warnings (media saved, embed check failed):[/]\n"
            body += "\n".join(f"  [dim]-[/] [yellow]{w}[/]" for w in warnings[:5])
        _show_error(
            f"{len(errors)} item(s) failed",
            body,
        )
    else:
        body = f"[dim]Downloaded:[/] {done}/{total} items"
        if warnings:
            body += "\n\n[bold yellow]Warnings (media saved, embed check failed):[/]\n"
            body += "\n".join(f"  [dim]-[/] [yellow]{w}[/]" for w in warnings[:5])
        _show_success(
            "Playlist Complete",
            body,
        )


# ── helpers ───────────────────────────────────────────────────────────────────


def _resolve_dir(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def _prompt_download_location(default: str | None = None) -> Path | None:
    if default is None:
        from vidsmith.settings.store import default_download_dir

        default = default_download_dir()
    default_dir = _resolve_dir(default)

    while True:
        console.print()
        console.print("[bold cyan]Download Location[/]")
        console.print(f"[dim]Press Enter to use {default_dir} or enter another directory.[/]")
        raw = Prompt.ask("Save to", default=str(default_dir)).strip()
        if raw.lower() in {"q", "quit", "exit"}:
            return None

        candidate = _resolve_dir(raw or str(default_dir))
        try:
            candidate.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            console.print(f"[error]Could not create that directory:[/] {exc}")
            continue

        if not candidate.is_dir():
            console.print(f"[error]That path is not a directory:[/] {candidate}")
            continue

        return candidate


def _progress_description(progress: DownloadProgress, media_type: str) -> str:
    if progress.stage == DownloadStage.FAILED:
        return progress.error or stage_label(progress.stage)
    if progress.message:
        return progress.message
    if progress.stage:
        return stage_label(progress.stage)
    return f"Downloading {media_type}"


def _progress_total_completed(progress: DownloadProgress) -> tuple[float | None, float, str]:
    indeterminate = {
        DownloadStage.EXTRACTING,
        DownloadStage.SELECTING,
        DownloadStage.RETRYING,
        DownloadStage.MERGING,
        DownloadStage.EMBEDDING_METADATA,
        DownloadStage.EMBEDDING_THUMBNAIL,
        DownloadStage.PROCESSING_SUBTITLES,
        DownloadStage.CLEANING,
    }
    if progress.stage in indeterminate:
        return None, 0.0, ""
    percent = max(0.0, min(100.0, progress.percent))
    if progress.stage == DownloadStage.COMPLETED:
        percent = 100.0
    return 100.0, percent, f"{percent:>3.0f}%"


def _progress_bytes(progress: DownloadProgress) -> str:
    if progress.total_bytes:
        return f"{_format_bytes(progress.bytes_downloaded)} / {_format_bytes(progress.total_bytes)}"
    if progress.bytes_downloaded:
        return _format_bytes(progress.bytes_downloaded)
    return ""


def _format_bytes(value: int | None) -> str:
    if not value:
        return "0 B"
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} PB"


def _media_duration(seconds: int) -> str:
    if seconds <= 0:
        return "Unknown"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _safe_filename(name: str) -> str:
    """Strip characters that are illegal in filenames."""
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ._-")
    return "".join(c if c in keep else "_" for c in name)[:120].strip() or "media"


def _parse_playlist_selection(
    item_selection: str,
    item_range: str,
    result: AnalysisResult,
) -> tuple[PlaylistSelectionMode, set[int], int | None, int | None]:
    if item_selection == "range" and item_range:
        range_start, range_end = _parse_range(item_range, result.item_count)
        return PlaylistSelectionMode.RANGE, set(), range_start, range_end
    if item_selection == "specific" and item_range:
        indices = _parse_indices(item_range)
        return PlaylistSelectionMode.SELECTED, indices, None, None
    return PlaylistSelectionMode.ALL, set(), None, None


def _parse_range(raw: str, total: int) -> tuple[int, int]:
    try:
        if "-" in raw:
            parts = raw.split("-", 1)
            return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, IndexError):
        pass
    return 1, total


def _parse_indices(raw: str) -> set[int]:
    result: set[int] = set()
    for token in raw.replace(" ", "").split(","):
        try:
            result.add(int(token))
        except ValueError:
            pass
    return result


def _progress_spinner(description: str) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold cyan]{description}[/]  {{task.description}}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )


def _show_success(title: str, body: str) -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup(body),
            title=f"[bold green] {title} [/]",
            border_style="green",
            padding=(1, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")


def _show_error(title: str, body: str) -> None:
    from vidsmith.settings.store import current_settings

    if current_settings().debug_logging:
        import logging
        import sys
        import traceback

        logger = logging.getLogger("vidsmith")
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_value is not None:
            logger.exception(f"{title}: {body}")
            console.print()
            console.print("[dim red]Traceback (most recent call last):[/]")
            for line in traceback.format_exception(exc_type, exc_value, exc_tb):
                console.print(f"[dim red]{line.rstrip()}[/]")
        else:
            logger.error(f"{title}: {body}")

    console.print()
    console.print(
        Panel(
            Text.from_markup(f"[error]{body}[/]"),
            title=f"[error] {title} [/]",
            border_style="red",
            padding=(0, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")


def _show_cancelled(
    body: str = "Download cancelled. Run the same download again to resume when possible.",
) -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup(f"[warning]{body}[/]"),
            title="[warning] Download Cancelled [/]",
            border_style="yellow",
            padding=(0, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")
