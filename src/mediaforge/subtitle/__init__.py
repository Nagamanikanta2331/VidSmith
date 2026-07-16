"""Shared subtitle language policy.

MediaForge supports exactly four subtitle languages. Every other language —
and every ``tlang=`` auto-translated track — is ignored throughout the app:
wizard choices, yt-dlp requests, and summary reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SUPPORTED_SUBTITLE_LANGUAGES: tuple[str, ...] = ("te", "hi", "ta", "en")

# Priority groups based on Phase C design. Custom downloads offer exactly this
# set (Indian languages + English) in this order; everything else is filtered.
PRIORITY_INDIAN: tuple[str, ...] = ("te", "hi", "ta", "mr", "bn", "ml", "pa", "gu", "ur")
PRIORITY_ENGLISH: tuple[str, ...] = ("en",)
# Custom-download order: the four supported languages first (te/hi/ta/en),
# then the remaining Indian languages.
PRIORITY_ALL: tuple[str, ...] = SUPPORTED_SUBTITLE_LANGUAGES + tuple(
    lang for lang in PRIORITY_INDIAN if lang not in SUPPORTED_SUBTITLE_LANGUAGES
)

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

# ffmpeg/ffprobe tag embedded streams with ISO 639-2 (three-letter) codes,
# while MediaForge requests ISO 639-1 (two-letter) codes. Needed to match
# "te" against an embedded "tel" stream and to tag streams we mux ourselves.
ISO_639_2: dict[str, str] = {
    "en": "eng",
    "hi": "hin",
    "te": "tel",
    "ta": "tam",
    "mr": "mar",
    "bn": "ben",
    "ml": "mal",
    "pa": "pan",
    "gu": "guj",
    "ur": "urd",
}


def language_matches(lang: str, candidates: "list[str] | set[str]") -> bool:
    """True when *lang* refers to the same language as any candidate code.

    Handles variants ("en-US" vs "en") and the two/three-letter code split
    ("ml" vs ffprobe's "mal") in both directions.
    """
    base = lang.split("-")[0].strip().lower()
    iso3 = ISO_639_2.get(base, "")
    for candidate in candidates:
        cand = candidate.split("-")[0].strip().lower()
        if cand in (lang.lower(), base, iso3):
            return True
        if cand.startswith(base) or base.startswith(cand):
            return True
    return False


def match_language(codes: list[str], lang: str) -> str | None:
    """Return the first code in *codes* that exactly matches *lang*."""
    for code in codes:
        if code == lang:
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

    If requested is None (Best Download), only the four supported languages
    are considered, manual variants first:
      1. The first manual track per supported language (exact code kept).
      2. Native auto subtitles for the remaining supported languages.
    Each requested track costs one throttled HTTP round-trip before media
    starts (``subtitle_delay_seconds`` × track count), so the list must stay
    small — never the full priority group.
    """
    selection = SubtitleSelection()
    wanted: list[str] = []

    if requested is not None:
        # User explicitly requested languages (e.g. transcript download)
        for code in requested:
            if code not in wanted:
                wanted.append(code)
    else:
        # Best Download: supported languages in priority order (te/hi/ta/en),
        # each resolved to its first manual variant when one exists.
        for base in SUPPORTED_SUBTITLE_LANGUAGES:
            manual = next(
                (
                    code
                    for code in manual_codes
                    if code.split("-")[0].strip().lower() == base
                ),
                None,
            )
            wanted.append(manual if manual is not None else base)

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
