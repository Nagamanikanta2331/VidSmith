from __future__ import annotations

from mediaforge.cli.wizard.base import Wizard
from mediaforge.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    TextInputStep,
    ToggleStep,
)
from mediaforge.settings.store import default_download_dir

_SOURCE_CHOICES = [
    Choice("Auto-generated", "auto", "AI captions from YouTube"),
    Choice("Manual captions", "manual", "Human-created subtitles"),
]

_LANG_CHOICES = [
    Choice("English", "en"),
    Choice("Spanish", "es"),
    Choice("French", "fr"),
    Choice("German", "de"),
    Choice("Japanese", "ja"),
    Choice("Korean", "ko"),
    Choice("Portuguese", "pt"),
    Choice("Auto-detect", "auto"),
]

_FORMAT_CHOICES = [
    Choice("TXT", "txt", "Plain text, one line per segment"),
    Choice("SRT", "srt", "SubRip — widely supported"),
    Choice("VTT", "vtt", "WebVTT — web standard"),
    Choice("JSON", "json", "Structured data with timestamps"),
]

_SUMMARY = [
    ("caption_source", "Caption Source"),
    ("language", "Language"),
    ("output_format", "Format"),
    ("include_timestamps", "Include Timestamps"),
    ("output_dir", "Save to"),
]


def build_transcript_wizard() -> Wizard:
    return Wizard(
        title="Extract Transcript",
        steps=[
            ChoiceStep(
                key="caption_source",
                title="Caption Source",
                choices=_SOURCE_CHOICES,
                default_index=0,
            ),
            ChoiceStep(
                key="language",
                title="Language",
                choices=_LANG_CHOICES,
                default_index=0,
            ),
            ChoiceStep(
                key="output_format",
                title="Output Format",
                choices=_FORMAT_CHOICES,
                default_index=0,
            ),
            ToggleStep(
                key="include_timestamps",
                title="Timestamps",
                prompt_label="Include timestamps in output?",
                default=False,
                description="Only available for TXT format.",
                # Only meaningful for plain text; SRT/VTT/JSON always carry timestamps
                skip_when=lambda s: s.get("output_format", "txt") != "txt",
            ),
            TextInputStep(
                key="output_dir",
                title="Output Directory",
                prompt_label="Save to",
                default=default_download_dir(),
            ),
            ConfirmationStep(summary_keys=_SUMMARY),
        ],
    )
