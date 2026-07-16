"""Shared Rich rendering helpers."""

from __future__ import annotations

from rich.align import Align
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from vidsmith.utils.console import console

LOGO = r"""
 █████   █████  ███      █████  █████████                   ███   █████    █████
░░███   ░░███  ░░░      ░░███  ███░░░░░███                 ░░░   ░░███    ░░███
 ░███    ░███  ████   ███████ ░███    ░░░  █████████████   ████  ███████   ░███████
 ░███    ░███ ░░███  ███░░███ ░░█████████ ░░███░░███░░███ ░░███ ░░░███░    ░███░░███
 ░░███   ███   ░███ ░███ ░███  ░░░░░░░░███ ░███ ░███ ░███  ░███   ░███     ░███ ░███
  ░░░█████░    ░███ ░███ ░███  ███    ░███ ░███ ░███ ░███  ░███   ░███ ███ ░███ ░███
    ░░███      █████░░████████░░█████████  █████░███ █████ █████  ░░█████  ████ █████
     ░░░      ░░░░░  ░░░░░░░░  ░░░░░░░░░  ░░░░░ ░░░ ░░░░░ ░░░░░    ░░░░░  ░░░░ ░░░░░

                                       VidSmith
"""


def print_banner() -> None:
    console.print(
        Align.center(
            Panel(
                # Left-justified so every row keeps its relative offset (the
                # block is centered as a whole by Align/Panel); no_wrap + crop
                # so a narrow console loses the edges instead of scrambling.
                Text(LOGO, style="bold bright_blue", no_wrap=True, overflow="crop"),
                subtitle="[dim]Production-grade media processing[/dim]",
                border_style="blue",
                padding=(0, 1),
            )
        )
    )


def print_rule(title: str = "") -> None:
    console.print(Rule(title, style="dim cyan"))


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_views(count: int) -> str:
    if count >= 1_000_000:
        return f"{count / 1_000_000:.1f}M"
    if count >= 1_000:
        return f"{count / 1_000:.1f}K"
    return str(count)
