"""Runtime capability detection for optional external tools.

MediaForge shells out to yt-dlp, which behaves differently depending on which
optional dependencies are present.  None of these are hard requirements, but
each one closes a specific quality gap versus the official yt-dlp CLI:

* ``curl_cffi``    - browser impersonation.  Without it YouTube prints
  "no impersonate target is available" and rate-limits subtitle/metadata
  requests more aggressively (HTTP 429).
* ``mutagen`` / ``AtomicParsley`` - proper cover-art atoms for MP4/M4A.
  Without either, yt-dlp embeds the thumbnail as an ffmpeg ``attached_pic``
  stream that Windows Explorer and several players do not render.
* a JavaScript runtime (``deno`` preferred, then ``node``) - required by
  modern yt-dlp to run YouTube's player JS.  Without it yt-dlp warns that
  "some formats may be missing".

These helpers are deliberately dependency-free and never raise; a missing tool
degrades gracefully into a friendly warning instead of a Python traceback.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
from shutil import which

# Runtimes are probed in preference order.  deno is yt-dlp's default enabled
# runtime; node works but must be explicitly enabled via the js_runtimes option.
_JS_RUNTIMES = ("deno", "node", "bun")


@lru_cache(maxsize=1)
def has_curl_cffi() -> bool:
    """True when the curl_cffi impersonation backend is importable."""
    return find_spec("curl_cffi") is not None


@lru_cache(maxsize=1)
def has_mutagen() -> bool:
    """True when mutagen (used for MP4/M4A cover-art atoms) is importable."""
    return find_spec("mutagen") is not None


@lru_cache(maxsize=1)
def has_atomicparsley() -> bool:
    """True when the AtomicParsley binary is on PATH."""
    return which("AtomicParsley") is not None or which("atomicparsley") is not None


@lru_cache(maxsize=1)
def available_js_runtime() -> str | None:
    """Return the highest-preference JavaScript runtime found on PATH, if any."""
    for runtime in _JS_RUNTIMES:
        if which(runtime):
            return runtime
    return None


def js_runtimes_option(node_path_override: str = "") -> dict[str, dict]:
    """yt-dlp ``js_runtimes`` value enabling the best available runtime.

    Returns an empty dict when only the default (``deno``) is present or nothing
    is available, so yt-dlp keeps its own default behaviour untouched.
    """
    if node_path_override:
        return {"node": {"binary": node_path_override}}

    runtime = available_js_runtime()
    # deno is already enabled by default in yt-dlp; only override to surface a
    # non-default runtime such as node/bun that the user happens to have.
    if runtime and runtime != "deno":
        return {runtime: {}}
    return {}


def can_embed_cover_atoms() -> bool:
    """True when MP4/M4A cover art can be written as a proper (visible) atom."""
    return has_mutagen() or has_atomicparsley()


def environment_warnings() -> list[str]:
    """Human-readable, actionable warnings for missing optional tooling.

    Empty when the environment is fully equipped.  Callers surface these once
    (e.g. before a download) rather than letting yt-dlp emit raw warnings.
    """
    warnings: list[str] = []

    if not has_curl_cffi():
        warnings.append(
            "Browser impersonation is unavailable (curl_cffi not installed). "
            "YouTube may rate-limit subtitles/metadata (HTTP 429). "
            "Install with:  pip install curl_cffi"
        )

    if not can_embed_cover_atoms():
        warnings.append(
            "Embedded thumbnails for MP4/M4A may not appear in Windows Explorer "
            "or some players (mutagen and AtomicParsley are both missing). "
            "Install with:  pip install mutagen"
        )

    if available_js_runtime() is None:
        warnings.append(
            "No JavaScript runtime found (deno/node). Some YouTube formats may "
            "be missing. Install Deno from https://deno.com for full parity."
        )

    return warnings
