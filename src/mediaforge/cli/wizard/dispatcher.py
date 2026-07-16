"""
Maps action keys (from cli/menus.py) to wizard factories, then executes the
result through the appropriate engine via cli.executor.

Built-in actions are registered in _BUILT_IN. The dispatcher then falls back
to WizardRegistry so AI plugins and third-party extensions register new actions
without touching this file.
"""

from __future__ import annotations

from collections.abc import Callable

from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from mediaforge.cli.wizard.base import (
    Wizard,
    WizardState,
)  # WizardState used for direct executor calls
from mediaforge.cli.wizard.registry import WizardRegistry
from mediaforge.cli.wizard.wizards import (
    build_audio_wizard,
    build_playlist_wizard,
    build_settings_wizard,
    build_transcript_wizard,
    build_video_wizard,
)
from mediaforge.models.media import AnalysisResult
from mediaforge.utils.console import console

_BUILT_IN: dict[str, Callable[[], Wizard]] = {
    "video": build_video_wizard,
    "audio": build_audio_wizard,
    "transcript": build_transcript_wizard,
    "playlist_video": build_playlist_wizard,
    "playlist_audio": build_playlist_wizard,
    "settings": build_settings_wizard,
}

# Maps action key → executor function (imported lazily to keep startup fast)
_EXECUTORS: dict[str, str] = {
    "video": "execute_video",
    "audio": "execute_audio",
    "transcript": "execute_transcript",
    "playlist_video": "execute_playlist",
    "playlist_audio": "execute_playlist",
}

# Actions that bypass the wizard entirely — executor is called directly.
_DIRECT_EXECUTORS: dict[str, str] = {
    "best_download": "execute_best_download",
    "best_playlist_download": "execute_best_playlist_download",
    "subtitles": "execute_subtitles",
    "thumbnail": "execute_thumbnail",
    "metadata": "execute_metadata",
}


def dispatch_wizard(action: str, result: AnalysisResult | None = None) -> None:
    """
    Resolve *action* to a wizard factory, run the wizard, then execute.

    Resolution order:
      1. Direct executors (_DIRECT_EXECUTORS) — skip the wizard entirely
      2. Built-in wizard table (_BUILT_IN)
      3. WizardRegistry (plugins / AI extensions)
      4. "Coming Soon" fallback
    """
    # Best Download and similar no-wizard flows go straight to the executor.
    direct_name = _DIRECT_EXECUTORS.get(action)
    if direct_name is not None:
        if result is not None:
            from mediaforge.cli import executor as _exec

            try:
                getattr(_exec, direct_name)(WizardState(), result)
            except Exception as exc:
                _exec._show_error("Execution Failed", str(exc))
        return

    factory = _BUILT_IN.get(action) or WizardRegistry.get(action)

    if factory is None:
        _show_coming_soon(action)
        return

    wizard = factory()
    initial: dict = {}
    if result is not None:
        initial["__media__"] = result

    final_state = wizard.run(initial=initial)

    if final_state is None:
        return  # user cancelled

    # Settings is media-independent: persist via its own executor, no result.
    if action == "settings":
        from mediaforge.cli import executor as _exec

        try:
            _exec.execute_settings(final_state)
        except Exception as exc:
            _exec._show_error("Settings Failed", str(exc))
        _show_settings_applied(wizard.title, final_state)
        return

    executor_name = _EXECUTORS.get(action)
    if executor_name is not None and result is not None:
        from mediaforge.cli import executor as _exec

        executor_fn = getattr(_exec, executor_name)
        try:
            executor_fn(final_state, result)
        except Exception as exc:
            _exec._show_error("Execution Failed", str(exc))
    else:
        # unknown non-download action: just show a summary
        _show_settings_applied(wizard.title, final_state)


# ── result screens ────────────────────────────────────────────────────────────


def _show_settings_applied(wizard_title: str, state: WizardState) -> None:
    """Shown for wizards that configure preferences (e.g. settings) rather than download."""
    from rich.table import Table

    summary = state.all()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", min_width=22)
    table.add_column(style="white")

    for key, raw in summary.items():
        display = state.get(f"__display_{key}")
        label = key.replace("_", " ").title()
        value = display if display is not None else str(raw)
        table.add_row(label, value)

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold green] {wizard_title} [/]",
            border_style="green",
            padding=(1, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to return to menu[/]", default="")


def _show_coming_soon(action: str) -> None:
    console.print()
    console.print(
        Panel(
            Text.from_markup(
                f"[bold cyan]Action:[/] [white]{action}[/]\n"
                "[dim]This wizard will be implemented in a future step.[/]"
            ),
            border_style="yellow",
            title="[yellow]Coming Soon[/]",
            padding=(1, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to return to menu[/]", default="")
