from __future__ import annotations

from mediaforge.cli.wizard.base import Wizard
from mediaforge.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    MultiSelectStep,
    TextInputStep,
)
from mediaforge.models.media import AnalysisResult
from mediaforge.settings.store import default_download_dir
from mediaforge.subtitle import PRIORITY_ALL, SUBTITLE_LANGUAGE_NAMES


_FORMAT_CHOICES = [
    Choice("VTT", "vtt", "WebVTT — web standard"),
    Choice("SRT", "srt", "SubRip — widely supported"),
    Choice("JSON", "json", "Structured JSON data"),
    Choice("TXT", "txt", "Plain text"),
]

_SUMMARY = [
    ("languages", "Languages"),
    ("output_format", "Format"),
    ("output_dir", "Save to"),
]


def build_subtitles_wizard(result: AnalysisResult | None = None) -> Wizard:
    # Offer only the priority languages (te/hi/ta/en + other Indian
    # languages), in policy order, each base language once — manual over
    # auto. Everything else is filtered to keep the request count (and the
    # YouTube rate-limit exposure) small.
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

    if not lang_choices:
        lang_choices = [Choice("None", "none")]

    return Wizard(
        title="Download Subtitles",
        steps=[
            MultiSelectStep(
                key="languages",
                title="Languages",
                choices=lang_choices,
                min_selections=1,
            ),
            ChoiceStep(
                key="output_format",
                title="Output Format",
                choices=_FORMAT_CHOICES,
                default_index=0,
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
