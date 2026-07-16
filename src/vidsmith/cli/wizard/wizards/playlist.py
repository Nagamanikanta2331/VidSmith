from __future__ import annotations

from vidsmith.cli.wizard.base import Wizard
from vidsmith.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    NumericStep,
    TextInputStep,
)
from vidsmith.settings.store import current_settings, default_download_dir

_SELECTION_CHOICES = [
    Choice("All items", "all", "Download the entire playlist"),
    Choice("Custom range", "range", "e.g. 1-10 or 3,7,12"),
    Choice("Specific items", "specific", "Choose items by number"),
]

_MEDIA_TYPE_CHOICES = [
    Choice("Video", "video", "Download as video files"),
    Choice("Audio only", "audio", "Extract audio track"),
]

_QUALITY_CHOICES = [
    Choice("Best Available", "best"),
    Choice("1080p  (HD)", "1080"),
    Choice("720p   (HD)", "720"),
    Choice("480p   (SD)", "480"),
    Choice("360p   (SD)", "360"),
]

_SUMMARY = [
    ("item_selection", "Items"),
    ("item_range", "Range"),
    ("media_type", "Media Type"),
    ("quality", "Quality"),
    ("output_dir", "Save to"),
    ("concurrency", "Parallel Downloads"),
]

_MAX_CONCURRENCY = 5


def _default_quality_index(choices: list[Choice]) -> int:
    """Index of the saved default quality in the static list; 'Best' fallback."""
    saved = current_settings().default_quality
    for i, choice in enumerate(choices):
        if choice.value == saved:
            return i
    return 0


def build_playlist_wizard() -> Wizard:
    s = current_settings()
    return Wizard(
        title="Playlist Download",
        steps=[
            ChoiceStep(
                key="item_selection",
                title="Item Selection",
                choices=_SELECTION_CHOICES,
                default_index=0,
            ),
            TextInputStep(
                key="item_range",
                title="Item Range",
                prompt_label="Range",
                default="1-10",
                description="Enter a range (1-10) or comma-separated indices (1,3,5).",
                skip_when=lambda s: s.get("item_selection") == "all",
            ),
            ChoiceStep(
                key="media_type",
                title="Media Type",
                choices=_MEDIA_TYPE_CHOICES,
                default_index=0,
            ),
            ChoiceStep(
                key="quality",
                title="Quality",
                choices=_QUALITY_CHOICES,
                default_index=_default_quality_index,
                skip_when=lambda s: s.get("media_type") == "audio",
            ),
            TextInputStep(
                key="output_dir",
                title="Output Directory",
                prompt_label="Save to",
                default=default_download_dir(),
                description="A sub-folder will be created for the playlist.",
            ),
            NumericStep(
                key="concurrency",
                title="Parallel Downloads",
                prompt_label="Simultaneous downloads",
                min_value=1,
                max_value=_MAX_CONCURRENCY,
                default=min(s.max_concurrency, _MAX_CONCURRENCY),
                unit="at a time",
                description="Higher values are faster but use more bandwidth.",
            ),
            ConfirmationStep(summary_keys=_SUMMARY),
        ],
    )
