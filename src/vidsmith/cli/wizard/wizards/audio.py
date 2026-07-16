from __future__ import annotations

from vidsmith.cli.wizard.base import Wizard, WizardState
from vidsmith.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    TextInputStep,
    ToggleStep,
)
from vidsmith.cli.wizard.wizards.video import get_language_name
from vidsmith.models.media import AnalysisResult
from vidsmith.settings.store import current_settings, default_download_dir

_FORMAT_CHOICES = [
    Choice("Original (no re-encode)", "original", "Keep the source codec — no quality loss"),
    Choice("MP3", "mp3", "Universal compatibility"),
    Choice("M4A", "m4a", "Apple ecosystem"),
    Choice("FLAC", "flac", "Lossless container (quality capped by source)"),
    Choice("OGG", "ogg", "Open format"),
    Choice("WAV", "wav", "Uncompressed PCM"),
]


def _default_format_index(choices: list[Choice]) -> int:
    """Index of the saved default audio format; 'Original' when unset/unknown."""
    saved = current_settings().default_audio_format
    for i, choice in enumerate(choices):
        if choice.value == saved:
            return i
    return 0


def _stream_label(codec: str, bitrate: float) -> str:
    codec_names = {
        "opus": "Opus",
        "mp4a.40.2": "AAC",
        "mp4a.40.5": "AAC-HE",
        "mp4a.40.29": "AAC-HE v2",
        "flac": "FLAC",
        "vorbis": "Vorbis",
        "ec-3": "Dolby Digital+",
        "ac-3": "Dolby Digital",
    }
    name = codec_names.get(codec.lower(), codec.split(".")[0].upper() if codec else "Audio")
    if bitrate > 0:
        return f"{name} · {round(bitrate)} kbps"
    return name


def _dynamic_stream_choices(state: WizardState) -> list[Choice]:
    """Build the source-stream menu from the real yt-dlp analysis.

    Every available audio-only stream is listed with codec, bitrate,
    language, and sample rate — nothing is hardcoded. Videos exposing FLAC
    or Dolby streams show them automatically.
    """
    result: AnalysisResult | None = state.get("__media__")
    choices = [Choice("Best available", "", "Highest quality audio stream")]
    if not result or not result.audio_streams:
        return choices

    for stream in result.audio_streams:
        details: list[str] = []
        if stream.language:
            details.append(get_language_name(stream.language))
        if stream.sample_rate:
            details.append(f"{stream.sample_rate / 1000:g} kHz")
        choices.append(
            Choice(
                _stream_label(stream.codec, stream.bitrate),
                stream.format_id,
                " · ".join(details),
            )
        )
    return choices


_SUMMARY = [
    ("output_dir", "Save to"),
    ("audio_stream_id", "Source Stream"),
    ("audio_format", "Format"),
    ("embed_thumbnail", "Embed Thumbnail"),
    ("embed_metadata", "Embed Metadata"),
]


def build_audio_wizard() -> Wizard:
    return Wizard(
        title="Audio Download",
        steps=[
            TextInputStep(
                key="output_dir",
                title="Output Directory",
                prompt_label="Save to",
                default=default_download_dir(),
                description="Directory where the audio file will be saved.",
            ),
            ChoiceStep(
                key="audio_stream_id",
                title="Audio Stream (from this video)",
                choices=_dynamic_stream_choices,
                default_index=0,
            ),
            ChoiceStep(
                key="audio_format",
                title="Output Format",
                choices=_FORMAT_CHOICES,
                default_index=_default_format_index,
            ),
            ToggleStep(
                key="embed_thumbnail",
                title="Embed Thumbnail",
                prompt_label="Embed thumbnail in audio file?",
                default=True,
                description="Cover art embedded in the file.",
                skip_when=lambda s: s.get("audio_format") == "wav",
            ),
            ToggleStep(
                key="embed_metadata",
                title="Embed Metadata",
                prompt_label="Embed title, artist, and album metadata?",
                default=True,
                skip_when=lambda s: s.get("audio_format") == "wav",
            ),
            ConfirmationStep(summary_keys=_SUMMARY),
        ],
    )
