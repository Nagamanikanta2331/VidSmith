from __future__ import annotations

from mediaforge.cli.wizard.base import Wizard, WizardState
from mediaforge.cli.wizard.steps import (
    Choice,
    ChoiceStep,
    ConfirmationStep,
    MultiSelectStep,
    TextInputStep,
    ToggleStep,
)
from mediaforge.models.media import AnalysisResult
from mediaforge.settings.store import current_settings, default_download_dir
from mediaforge.subtitle import (
    SUBTITLE_LANGUAGE_NAMES,
    SUPPORTED_SUBTITLE_LANGUAGES,
    base_language,
    is_supported_language,
)

_LANG_NAMES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "ar": "Arabic",
    "bn": "Bengali",
    "nl": "Dutch",
    "el": "Greek",
    "he": "Hebrew",
    "id": "Indonesian",
    "pl": "Polish",
    "sv": "Swedish",
    "th": "Thai",
    "tr": "Turkish",
    "vi": "Vietnamese",
}


def get_language_name(code: str) -> str:
    base_code = code.split("-")[0].lower()
    return _LANG_NAMES.get(base_code, code.upper())


def _resolution_label(res: str) -> str:
    """'1920x1080' → '1080p', '720p' stays '720p'; unknown shapes pass through."""
    if "x" in res:
        height = res.rpartition("x")[2].strip()
        if height.isdigit():
            return f"{height}p"
    return res


def _dynamic_quality_choices(state: WizardState) -> list[Choice]:
    result: AnalysisResult | None = state.get("__media__")
    choices = [Choice("Best Available", "best", "Highest quality the source offers")]
    if result and result.resolutions:
        descriptions = {
            "4320": "8K Ultra HD",
            "2160": "4K Ultra HD",
            "1440": "Quad HD",
            "1080": "Full HD",
            "720": "HD",
            "480": "Standard Definition",
            "360": "Low bandwidth",
        }
        for res in result.resolutions:
            label = _resolution_label(res)
            desc = descriptions.get(label.rstrip("p"), "")
            choices.append(Choice(label, res, desc))
    return choices


def _dynamic_format_choices(state: WizardState) -> list[Choice]:
    result: AnalysisResult | None = state.get("__media__")
    all_mapped = {
        "mp4": Choice("MP4", "mp4", "Best compatibility"),
        "mkv": Choice("MKV", "mkv", "Preserves all streams"),
        "webm": Choice("WebM", "webm", "Open format"),
    }
    if not result or not result.containers:
        return [all_mapped["mp4"], all_mapped["mkv"], all_mapped["webm"]]

    # yt-dlp reports source containers like "mp4_dash"/"webm_dash"; match on
    # the prefix. MKV is always offered — it is a merge target that accepts
    # any source codec, not a source container.
    available = [c.lower() for c in result.containers]
    choices = []
    for ext in ["mp4", "mkv", "webm"]:
        if ext == "mkv":
            choices.append(all_mapped[ext])
            continue
        if any(container.startswith(ext) for container in available):
            choices.append(all_mapped[ext])
    return choices


def _dynamic_subtitle_choices(state: WizardState) -> list[Choice]:
    """One choice per supported language (en/hi/te/ta), manual over auto.

    A language backed only by auto-generated captions is labelled
    "<Name> (Auto)"; unavailable languages are omitted, so each language
    appears at most once. Values are base language codes — the job builder
    re-resolves the exact source track.
    """
    result: AnalysisResult | None = state.get("__media__")
    if not result:
        return []

    manual_bases = {
        base_language(code)
        for code in (result.subtitle_languages or [])
        if is_supported_language(code)
    }
    auto_bases = {
        base_language(code)
        for code in (result.automatic_subtitle_languages or [])
        if is_supported_language(code)
    }

    choices = []
    for base in SUPPORTED_SUBTITLE_LANGUAGES:
        name = SUBTITLE_LANGUAGE_NAMES[base]
        if base in manual_bases:
            choices.append(Choice(name, base, "Manual"))
        elif base in auto_bases:
            choices.append(Choice(f"{name} (Auto)", base, "Auto-generated"))
    return choices


def _has_no_subtitles(state: WizardState) -> bool:
    result: AnalysisResult | None = state.get("__media__")
    if not result:
        return True
    all_subs = (result.subtitle_languages or []) + (result.automatic_subtitle_languages or [])
    return not any(is_supported_language(code) for code in all_subs)


def _dynamic_audio_choices(state: WizardState) -> list[Choice]:
    result: AnalysisResult | None = state.get("__media__")
    if not result or not result.audio_languages:
        return [Choice("Default / English", "en")]

    choices = []
    seen_names = set()
    for code in result.audio_languages:
        name = get_language_name(code)
        if name not in seen_names:
            seen_names.add(name)
            choices.append(Choice(name, code))
    return choices


def _skip_audio_lang_step(state: WizardState) -> bool:
    result: AnalysisResult | None = state.get("__media__")
    if not result or not result.audio_languages:
        return True
    return len(result.audio_languages) <= 1


def _default_quality_index(choices: list[Choice]) -> int:
    """Index of the saved default quality ("best"/"1080"/…) in the dynamic list.

    Dynamic choices carry raw source resolutions ("1920x1080") with labels like
    "1080p", so match on the height embedded in the label. Falls back to
    "Best Available" (index 0) when the saved height isn't offered.
    """
    saved = current_settings().default_quality
    if saved == "best":
        return 0
    for i, choice in enumerate(choices):
        if choice.value == "best":
            continue
        if _resolution_label(str(choice.value)).rstrip("p") == saved:
            return i
    return 0


def _default_format_index(choices: list[Choice]) -> int:
    """Index of the saved default container in the dynamic format list."""
    saved = current_settings().default_container
    for i, choice in enumerate(choices):
        if choice.value == saved:
            return i
    return 0


_SUMMARY = [
    ("output_dir", "Save to"),
    ("quality", "Quality"),
    ("format", "Format"),
    ("thumbnail_mode", "Thumbnail"),
    ("include_subtitles", "Include Subtitles"),
    ("subtitle_langs", "Subtitle Languages"),
    ("audio_lang", "Audio Language"),
]


def build_video_wizard() -> Wizard:
    return Wizard(
        title="Video Download",
        steps=[
            TextInputStep(
                key="output_dir",
                title="Output Directory",
                prompt_label="Save to",
                default=default_download_dir(),
                description="Directory where the video file will be saved.",
            ),
            ChoiceStep(
                key="quality",
                title="Video Quality",
                choices=_dynamic_quality_choices,
                default_index=_default_quality_index,
            ),
            ChoiceStep(
                key="format",
                title="Video Format",
                choices=_dynamic_format_choices,
                default_index=_default_format_index,
            ),
            ChoiceStep(
                key="thumbnail_mode",
                title="Thumbnail Options",
                choices=[
                    Choice("Embed into video", "embed", "Include cover art inside the file (default)"),
                    Choice("Save separately", "save", "Save as a separate image file"),
                    Choice("Both", "both", "Embed and save separately"),
                    Choice("None", "none", "Do not download thumbnail"),
                ],
                default_index=0,
            ),
            ToggleStep(
                key="include_subtitles",
                title="Subtitles",
                prompt_label="Download subtitles?",
                default=False,
                description="Subtitle files will be saved alongside the video.",
                skip_when=_has_no_subtitles,
            ),
            MultiSelectStep(
                key="subtitle_langs",
                title="Subtitle Options",
                choices=_dynamic_subtitle_choices,
                min_selections=1,
                skip_when=lambda s: not s.get("include_subtitles", False) or _has_no_subtitles(s),
            ),
            ChoiceStep(
                key="audio_lang",
                title="Audio Language",
                choices=_dynamic_audio_choices,
                default_index=0,
                skip_when=_skip_audio_lang_step,
            ),
            ConfirmationStep(summary_keys=_SUMMARY),
        ],
    )
