from __future__ import annotations

from vidsmith.cli.wizard.base import Wizard
from vidsmith.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    TextInputStep,
    ToggleStep,
)
from vidsmith.models.media import AnalysisResult
from vidsmith.settings.store import default_download_dir
from vidsmith.subtitle import PRIORITY_ALL, SUBTITLE_LANGUAGE_NAMES

_SOURCE_CHOICES = [
    Choice("Auto-generated", "auto", "AI captions from YouTube"),
    Choice("Manual captions", "manual", "Human-created subtitles"),
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


def build_transcript_wizard(result: AnalysisResult | None = None) -> Wizard:
    # Same priority-language filter as the subtitles wizard: te/hi/ta/en plus
    # the other Indian languages, one entry per base language, manual first.
    lang_choices = []
    if result:
        manual = result.subtitle_languages or []
        auto = result.automatic_subtitle_languages or []

        def _first_match(codes: list[str], base: str) -> str | None:
            for code in codes:
                if code.split("-")[0].strip().lower() == base:
                    return code
            return None

        for base in PRIORITY_ALL:
            name = SUBTITLE_LANGUAGE_NAMES.get(base, base.upper())
            code = _first_match(manual, base)
            if code is not None:
                lang_choices.append(Choice(name, code, "Manual"))
                continue
            code = _first_match(auto, base)
            if code is not None:
                lang_choices.append(Choice(f"{name} (Auto)", code, "Auto-generated"))

    # If no languages found at all, we must provide at least one choice to not crash the wizard
    if not lang_choices:
        lang_choices = [Choice("None", "none")]

    lang_choices.append(Choice("Auto-detect", "auto"))

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
                choices=lang_choices,
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
