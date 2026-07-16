"""
Interactive application loop.
Entry: run()
Flow: banner → URL prompt → analyse (spinner) → type-dispatch → menu → wizard loop
"""

from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Prompt
from rich.status import Status
from rich.text import Text

from vidsmith.cli.menus import (
    ACTION_BACK,
    show_playlist_menu,
    show_video_menu,
)
from vidsmith.cli.output import print_banner, print_rule
from vidsmith.cli.wizard.dispatcher import dispatch_wizard
from vidsmith.metadata.analyzer import analyze
from vidsmith.models.media import AnalysisResult, MediaType
from vidsmith.utils.console import console
from vidsmith.utils.exceptions import AnalysisError, UnsupportedURLError
from vidsmith.utils.validators import is_youtube_url

# ── URL collection ────────────────────────────────────────────────────────────


def _prompt_url() -> str | None:
    """Show URL input prompt. Returns None when the user quits.

    Returns the sentinel ``"__settings__"`` when the user asks for settings.
    """
    console.print()
    print_rule()
    console.print(
        Panel(
            Text.from_markup(
                "[dim]Paste a YouTube URL and press[/] [bold cyan]Enter[/]\n"
                "[dim]Type[/] [bold]s[/] [dim]for Settings ·[/] [bold]q[/] [dim]to quit[/]"
            ),
            border_style="dim",
            padding=(1, 4),
        )
    )
    console.print()

    raw = Prompt.ask("  [bold cyan]URL[/]").strip()
    if raw.lower() in {"q", "quit", "exit"}:
        return None
    if raw.lower() in {"s", "settings"}:
        return "__settings__"
    return raw


# ── analysis ──────────────────────────────────────────────────────────────────


def _analyse_url(url: str) -> AnalysisResult | None:
    """
    Run URL analysis under a Rich spinner.
    Returns None and prints an error on failure.
    """
    if not is_youtube_url(url):
        console.print(
            Panel(
                Text.from_markup(
                    "[error]Not a recognised YouTube URL.[/]\n"
                    "[dim]Supported: youtube.com/watch, youtu.be, /shorts/, /playlist[/]"
                ),
                border_style="red",
                title="[error]Invalid URL[/]",
                padding=(0, 2),
            )
        )
        return None

    with Status(
        "[bold cyan]Analysing URL…[/]",
        spinner="dots",
        spinner_style="cyan",
        console=console,
    ):
        try:
            return analyze(url)
        except UnsupportedURLError as exc:
            _print_error("Unsupported URL", str(exc))
            return None
        except AnalysisError as exc:
            _print_error("Analysis Failed", str(exc))
            return None
        except Exception as exc:
            _print_error("Unexpected Error", str(exc))
            return None


def _print_error(title: str, body: str) -> None:
    console.print(
        Panel(
            f"[error]{body}[/]",
            title=f"[error]{title}[/]",
            border_style="red",
            padding=(0, 2),
        )
    )


# ── type-dispatch ─────────────────────────────────────────────────────────────


def _show_menu(result: AnalysisResult) -> str | None:
    if result.media_type == MediaType.PLAYLIST:
        return show_playlist_menu(result)
    return show_video_menu(result)  # VIDEO and SHORTS share the same menu


# ── action handler ────────────────────────────────────────────────────────────


def _handle_action(action: str, result: AnalysisResult) -> None:
    dispatch_wizard(action, result)


# ── main loop ─────────────────────────────────────────────────────────────────


def run() -> None:
    console.clear()
    print_banner()

    from vidsmith.settings.store import reload_settings

    reload_settings()

    try:
        while True:
            try:
                url = _prompt_url()
            except KeyboardInterrupt:
                _goodbye()
                break

            if url is None:
                _goodbye()
                break

            if url == "__settings__":
                dispatch_wizard("settings")
                continue

            result = _analyse_url(url)
            if result is None:
                continue  # bad URL → re-prompt

            # Inner menu loop: stay on the same result until user goes Back or Quits
            while True:
                try:
                    action = _show_menu(result)

                    if action is None:  # user chose Quit
                        _goodbye()
                        return

                    if action == ACTION_BACK:  # user chose Back → outer loop
                        break

                    _handle_action(action, result)
                except KeyboardInterrupt:
                    console.print("\n  [yellow]Action cancelled.[/]")
    except KeyboardInterrupt:
        _goodbye()


def _goodbye() -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup("[bold cyan]Thanks for using VidSmith. Goodbye![/]"),
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()
