from __future__ import annotations

from pathlib import Path

from vidsmith.cli.wizard.base import Wizard
from vidsmith.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    NumericStep,
    TextInputStep,
    ToggleStep,
)
from vidsmith.settings.store import current_settings

_QUALITY_CHOICES = [
    Choice("Best Available", "best"),
    Choice("1080p  (HD)", "1080"),
    Choice("720p   (HD)", "720"),
    Choice("480p   (SD)", "480"),
    Choice("360p   (SD)", "360"),
]

_AUDIO_FORMAT_CHOICES = [
    Choice("MP3", "mp3"),
    Choice("M4A", "m4a"),
    Choice("FLAC", "flac"),
    Choice("OGG", "ogg"),
    Choice("WAV", "wav"),
]

_AUDIO_QUALITY_CHOICES = [
    Choice("320 kbps", "320k"),
    Choice("256 kbps", "256k"),
    Choice("192 kbps", "192k"),
    Choice("128 kbps", "128k"),
]

_CONTAINER_CHOICES = [
    Choice("MP4", "mp4", "Best compatibility"),
    Choice("MKV", "mkv", "Preserves all streams"),
    Choice("WebM", "webm", "Open format"),
]

_SUBTITLE_DELAY_CHOICES = [
    Choice("Off (0s)", "0"),
    Choice("5 seconds", "5"),
    Choice("10 seconds", "10"),
    Choice("15 seconds", "15"),
    Choice("Custom", "custom"),
]

_SUMMARY = [
    ("default_output_directory", "Default Save Location"),
    ("default_container", "Default Container"),
    ("default_quality", "Default Video Quality"),
    ("default_audio_format", "Default Audio Format"),
    ("default_audio_quality", "Default Audio Bitrate"),
    ("subtitle_delay_mode", "Subtitle Delay"),
    ("cleanup_enabled", "Cleanup Temp Files"),
    ("keep_temp_files", "Keep Temp Files"),
    ("node_path_override", "Node.js Path"),
    ("ffmpeg_path_override", "FFmpeg Path"),
    ("max_concurrency", "Max Parallel Downloads"),
    ("debug_logging", "Debug Logging"),
]


def _index_of(choices: list[Choice], value: object, fallback: int = 0) -> int:
    for i, choice in enumerate(choices):
        if choice.value == value:
            return i
    return fallback


def _optional_path_validator(value: str) -> str | None:
    """Accept an empty string (unset) or a path that exists on disk."""
    if not value:
        return None
    if Path(value).expanduser().exists():
        return None
    return f"Path does not exist: {value}"


def build_settings_wizard() -> Wizard:
    s = current_settings()
    return Wizard(
        title="Settings",
        steps=[
            TextInputStep(
                key="default_output_directory",
                title="Default Save Location",
                prompt_label="Default directory",
                default=s.default_output_directory or "~/Downloads",
                description="All wizards will default to this directory.",
            ),
            ChoiceStep(
                key="default_container",
                title="Default Container",
                choices=_CONTAINER_CHOICES,
                default_index=_index_of(_CONTAINER_CHOICES, s.default_container),
            ),
            ChoiceStep(
                key="default_quality",
                title="Default Video Quality",
                choices=_QUALITY_CHOICES,
                default_index=_index_of(_QUALITY_CHOICES, s.default_quality, 1),
            ),
            ChoiceStep(
                key="default_audio_format",
                title="Default Audio Format",
                choices=_AUDIO_FORMAT_CHOICES,
                default_index=_index_of(_AUDIO_FORMAT_CHOICES, s.default_audio_format),
            ),
            ChoiceStep(
                key="default_audio_quality",
                title="Default Audio Bitrate",
                choices=_AUDIO_QUALITY_CHOICES,
                default_index=_index_of(_AUDIO_QUALITY_CHOICES, s.default_audio_quality, 2),
            ),
            ChoiceStep(
                key="subtitle_delay_mode",
                title="Subtitle Delay",
                choices=_SUBTITLE_DELAY_CHOICES,
                default_index=_index_of(
                    _SUBTITLE_DELAY_CHOICES,
                    str(s.subtitle_delay_seconds),
                    _index_of(_SUBTITLE_DELAY_CHOICES, "custom"),
                ),
            ),
            NumericStep(
                key="subtitle_delay_custom",
                title="Custom Subtitle Delay",
                prompt_label="Seconds between subtitle requests",
                min_value=0,
                max_value=15,
                default=min(s.subtitle_delay_seconds, 15),
                unit="s",
                description=(
                    "Throttle to avoid YouTube rate-limiting (429). Applied "
                    "before EACH subtitle track, so total wait ≈ delay × tracks "
                    "(up to 4). Max 15s."
                ),
                skip_when=lambda state: state.get("subtitle_delay_mode") != "custom",
            ),
            ToggleStep(
                key="cleanup_enabled",
                title="Cleanup Temp Files",
                prompt_label="Delete temporary files after a successful download?",
                default=s.cleanup_enabled,
                description="Removes .part, .webp, .vtt, .info.json once embedded.",
            ),
            ToggleStep(
                key="keep_temp_files",
                title="Keep Temp Files",
                prompt_label="Always keep temporary files (for debugging)?",
                default=s.keep_temp_files,
                description="Overrides cleanup — useful when diagnosing subtitle issues.",
            ),
            TextInputStep(
                key="node_path_override",
                title="Node.js Path",
                prompt_label="Node.js binary path (blank = auto-detect)",
                default=s.node_path_override,
                validator=_optional_path_validator,
                allow_empty=True,
                description="Point at a specific node binary, or leave blank to use PATH.",
            ),
            TextInputStep(
                key="ffmpeg_path_override",
                title="FFmpeg Path",
                prompt_label="FFmpeg binary path (blank = auto-detect)",
                default=s.ffmpeg_path_override,
                validator=_optional_path_validator,
                allow_empty=True,
                description="Point at a specific ffmpeg binary, or leave blank to use PATH.",
            ),
            NumericStep(
                key="max_concurrency",
                title="Max Parallel Downloads",
                prompt_label="Max simultaneous",
                min_value=1,
                max_value=8,
                default=s.max_concurrency,
                unit="downloads",
                description="Global cap applied to all playlist operations.",
            ),
            ToggleStep(
                key="debug_logging",
                title="Debug Logging",
                prompt_label="Enable verbose file logging?",
                default=s.debug_logging,
                description="Writes detailed logs to %APPDATA%/VidSmith/vidsmith.log.",
            ),
            ConfirmationStep(summary_keys=_SUMMARY),
        ],
    )
