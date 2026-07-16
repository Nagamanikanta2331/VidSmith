"""``mediaforge doctor`` — environment diagnostics.

Inspects every optional and required tool MediaForge relies on and prints a
clear, colour-coded report with actionable install hints.  Modelled on
``brew doctor`` / ``gh`` status output.  It never raises: any probe that fails
is reported as a failed check rather than crashing the command.
"""

from __future__ import annotations

import platform
import shutil
import socket
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from mediaforge.config import APP_NAME, APP_VERSION
from mediaforge.utils.console import console

_OK = "ok"
_WARN = "warn"
_FAIL = "fail"

_MARKS = {_OK: "[green]✓[/]", _WARN: "[yellow]⚠[/]", _FAIL: "[red]✗[/]"}


@dataclass(slots=True)
class Check:
    """A single diagnostic row."""

    name: str
    status: str
    detail: str = ""
    hint: str = ""


# ── individual probes (each returns a Check, never raises) ────────────────────


def _check_python() -> Check:
    version_text = platform.python_version()
    if sys.version_info >= (3, 12):
        return Check("Python", _OK, version_text)
    return Check(
        "Python",
        _FAIL,
        f"{version_text} (3.12+ required)",
        "Install Python 3.12 or newer from https://python.org",
    )


def _check_package(
    name: str,
    module: str,
    dist: str,
    *,
    required: bool,
    hint: str,
) -> Check:
    """Report on an importable Python package by distribution name."""
    spec_present = find_spec(module) is not None
    if not spec_present:
        return Check(name, _FAIL if required else _WARN, "Not installed", hint)
    try:
        detail = version(dist)
    except PackageNotFoundError:
        detail = "installed"
    return Check(name, _OK, detail)


def _check_binary(
    name: str,
    candidates: tuple[str, ...],
    *,
    required: bool,
    hint: str,
) -> Check:
    """Report on an external executable resolved from PATH."""
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return Check(name, _OK, path)
    return Check(name, _FAIL if required else _WARN, "Not installed", hint)


def _check_ffmpeg() -> Check:
    check = _check_binary(
        "FFmpeg",
        ("ffmpeg",),
        required=False,
        hint="Install FFmpeg from https://ffmpeg.org (or `pip install imageio-ffmpeg`).",
    )
    if check.status != _OK:
        # imageio-ffmpeg provides a bundled binary as a fallback.
        try:
            import imageio_ffmpeg

            return Check("FFmpeg", _OK, f"bundled: {imageio_ffmpeg.get_ffmpeg_exe()}")
        except Exception:
            pass
    return check


def _check_socket(host: str, name: str, ok_detail: str) -> Check:
    try:
        socket.setdefaulttimeout(6)
        with socket.create_connection((host, 443)):
            return Check(name, _OK, ok_detail)
    except OSError as exc:
        return Check(
            name, _WARN, f"Unreachable ({exc.__class__.__name__})", "Check your network connection."
        )


def collect_checks(*, network: bool = True) -> list[Check]:
    """Run every diagnostic and return the ordered result list."""
    checks: list[Check] = [
        _check_python(),
        _check_package(
            "yt-dlp",
            "yt_dlp",
            "yt-dlp",
            required=True,
            hint="Reinstall MediaForge or run `pip install -U yt-dlp`.",
        ),
        _check_ffmpeg(),
        _check_package(
            "curl_cffi",
            "curl_cffi",
            "curl_cffi",
            required=False,
            hint="`pip install curl_cffi` — enables browser impersonation and reduces HTTP 429.",
        ),
        _check_package(
            "mutagen",
            "mutagen",
            "mutagen",
            required=False,
            hint="`pip install mutagen` — writes MP4/M4A cover-art atoms visible in Explorer.",
        ),
        _check_binary(
            "AtomicParsley",
            ("AtomicParsley", "atomicparsley"),
            required=False,
            hint="Optional alternative to mutagen for MP4 cover art.",
        ),
        _check_binary(
            "Node.js",
            ("node",),
            required=False,
            hint="Optional JavaScript runtime; Deno is preferred.",
        ),
        _check_binary(
            "Deno",
            ("deno",),
            required=False,
            hint="`https://deno.com` — recommended JS runtime for full YouTube format parity.",
        ),
    ]
    if network:
        checks.append(_check_socket("one.one.one.one", "Internet", "Connected"))
        checks.append(_check_socket("www.youtube.com", "YouTube Access", "Reachable"))
    return checks


def run_doctor(*, network: bool = True) -> int:
    """Render the diagnostics report. Returns a process exit code.

    Exit code is non-zero only when a *required* check fails, so scripts and CI
    can gate on it; optional-tool warnings keep the exit code at 0.
    """
    checks = collect_checks(network=network)

    table = Table.grid(padding=(0, 2))
    table.add_column(justify="center", no_wrap=True)
    table.add_column(style="bold", no_wrap=True)
    table.add_column(style="white")
    for check in checks:
        table.add_row(_MARKS.get(check.status, "?"), check.name, check.detail)

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold cyan] {APP_NAME} Doctor · v{APP_VERSION} [/]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    hints = [check for check in checks if check.status != _OK and check.hint]
    if hints:
        lines = [
            f"{_MARKS[check.status]} [bold]{check.name}[/] — {check.detail or 'unavailable'}\n"
            f"   [dim]{check.hint}[/]"
            for check in hints
        ]
        console.print(
            Panel(
                Text.from_markup("\n".join(lines)),
                title="[yellow] Recommendations [/]",
                border_style="yellow",
                padding=(1, 2),
            )
        )
    else:
        console.print("[green]Everything looks good — MediaForge is fully equipped.[/]\n")

    has_required_failure = any(
        check.status == _FAIL and check.name in {"Python", "yt-dlp"} for check in checks
    )
    return 1 if has_required_failure else 0
