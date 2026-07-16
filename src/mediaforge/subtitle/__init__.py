"""Shared subtitle language policy.

MediaForge supports exactly four subtitle languages. Every other language —
and every ``tlang=`` auto-translated track — is ignored throughout the app:
wizard choices, yt-dlp requests, and summary reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SUPPORTED_SUBTITLE_LANGUAGES: tuple[str, ...] = ("en", "hi", "te", "ta")

# Priority groups based on Phase C design. Used for sorting, not filtering.
PRIORITY_INDIAN: tuple[str, ...] = ("hi", "te", "ta", "mr", "bn", "ml", "pa", "gu", "ur")
PRIORITY_ENGLISH: tuple[str, ...] = ("en",)
PRIORITY_ALL = PRIORITY_INDIAN + PRIORITY_ENGLISH

SUBTITLE_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ta": "Tamil",
    "mr": "Marathi",
    "bn": "Bengali",
    "ml": "Malayalam",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "ur": "Urdu",
}


def base_language(code: str) -> str:
    """Normalize a language tag to its base code: ``en-US`` → ``en``."""
    return code.split("-")[0].strip().lower()


def is_supported_language(code: str) -> bool:
    """Return True if this language is a priority language."""
    return base_language(code) in PRIORITY_ALL


def match_language(codes: list[str], lang: str) -> str | None:
    """Return the first code in *codes* whose base language is *lang*."""
    for code in codes:
        if base_language(code) == lang:
            return code
    return None


@dataclass(slots=True)
class SubtitleSelection:
    """Resolved subtitle plan for one download job."""

    # Exact source codes to request from yt-dlp (manual or auto).
    codes: list[str] = field(default_factory=list)
    # Requested base codes, in policy order (drives summary reporting).
    requested: list[str] = field(default_factory=list)
    # Base codes resolved to auto-generated captions (for "(Auto)" labels).
    auto_languages: list[str] = field(default_factory=list)
    # Requested base codes with no manual or auto track — skipped silently.
    unavailable: list[str] = field(default_factory=list)


def resolve_subtitle_selection(
    manual_codes: list[str],
    auto_codes: list[str],
    requested: list[str] | None = None,
) -> SubtitleSelection:
    """Apply the language policy: manual wins, then auto, then translated.

    *manual_codes*/*auto_codes* must exclude ``tlang=`` translated tracks (unless
    explicitly allowed for priority languages). *requested* holds base language codes.
    If requested is None, we apply the Priority Groups logic:
      1. All native/manual tracks.
      2. Native auto subtitles ONLY for priority languages.
      3. Auto-translated subtitles ONLY for priority languages (if not covered above).
    """
    selection = SubtitleSelection()
    wanted: list[str] = []

    if requested is not None:
        # User explicitly requested languages (e.g. transcript download)
        for code in requested:
            lang = base_language(code)
            if lang not in wanted:
                wanted.append(lang)
    else:
        # Priority Group logic for Best Download
        # 1. All native/manual tracks
        for code in manual_codes:
            lang = base_language(code)
            if lang not in wanted:
                wanted.append(lang)

        # 2 & 3. Auto/Translated for priority languages
        for lang in PRIORITY_ALL:
            if lang not in wanted:
                wanted.append(lang)

    selection.requested = wanted

    for lang in wanted:
        # Group 1: Native/manual wins
        manual = match_language(manual_codes, lang)
        if manual is not None:
            selection.codes.append(manual)
            continue

        # Group 2: Native auto subtitles
        # For Best Download (requested is None), only fetch auto for priority languages
        if requested is None and lang not in PRIORITY_ALL:
            selection.unavailable.append(lang)
            continue

        auto = match_language(auto_codes, lang)
        if auto is not None:
            selection.codes.append(auto)
            selection.auto_languages.append(lang)
            continue

        # If we reach here, it's unavailable (we rely on yt-dlp handling translated natively
        # or it's absent completely)
        selection.unavailable.append(lang)

    return selection
