"""
Shared UI chrome rendered around every wizard step.

Public API:
  render_wizard_header(ctx)          – clears screen, draws header panel + rule
  render_nav_footer(is_first, confirm) – draws divider + nav hint row
  render_summary_table(rows)         – returns a Panel for ConfirmationStep
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from mediaforge.cli.wizard.base import StepContext
from mediaforge.utils.console import console

# ── header ────────────────────────────────────────────────────────────────────


def render_wizard_header(ctx: StepContext) -> None:
    """Clear the terminal and draw the wizard chrome above the step content."""
    console.clear()
    console.print()

    dots = _progress_dots(ctx.step_num, ctx.total_visible)

    title_row = Table.grid(padding=(0, 1))
    title_row.add_column(ratio=1)
    title_row.add_column(justify="right")
    title_row.add_row(
        Text(ctx.wizard_title, style="bold white"),
        dots,
    )

    media = ctx.state.get("__media__")
    inner: object
    if media is not None:
        inner = Group(title_row, Text(""), _media_summary(media))
    else:
        inner = title_row

    console.print(Panel(inner, border_style="cyan", padding=(0, 2)))
    console.print()
    console.print(
        Rule(
            f"[bold white]{ctx.step_title}[/]",
            style="dim cyan",
        )
    )
    console.print()


# ── footer ────────────────────────────────────────────────────────────────────


def render_nav_footer(*, is_first: bool = False, confirm: bool = False) -> None:
    """Draw the navigation hint bar at the bottom of each step."""
    console.print()
    console.print(Rule(style="dim"))

    nav = Table.grid(padding=(0, 3))
    nav.add_column(min_width=18)
    nav.add_column(min_width=18)
    nav.add_column(min_width=14)

    prev_text = Text("p  Previous", style="dim") if not is_first else Text("")
    next_label = "Enter  Confirm" if confirm else "Enter  Next"
    next_text = Text(next_label, style="bold cyan")
    cancel_text = Text("c  Cancel", style="dim")

    nav.add_row(prev_text, next_text, cancel_text)
    console.print("  ", nav)
    console.print()


# ── summary panel (used by ConfirmationStep) ──────────────────────────────────


def render_summary_table(rows: list[tuple[str, str]]) -> Panel:
    """Return a Rich Panel containing a two-column summary table."""
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=False,
    )
    table.add_column(style="dim", min_width=22)
    table.add_column(style="bold white")

    for label, value in rows:
        table.add_row(label, value)

    return Panel(
        table,
        title="[bold white]Review Your Choices[/]",
        border_style="cyan",
        padding=(1, 2),
    )


# ── internal helpers ──────────────────────────────────────────────────────────


def _progress_dots(current: int, total: int) -> Text:
    t = Text()
    for i in range(1, total + 1):
        if i < current:
            t.append("[#] ", style="dim cyan")
        elif i == current:
            t.append("[*] ", style="bold cyan")
        else:
            t.append("[ ] ", style="dim")
    return t


def _media_summary(media: object) -> Table:
    from mediaforge.cli.output import format_duration
    from mediaforge.models.media import MediaType

    grid = Table.grid(padding=(0, 3))
    grid.add_column(style="dim", min_width=10)
    grid.add_column()

    grid.add_row("Title", f"[bold white]{getattr(media, 'title', '')}[/]")
    grid.add_row("Channel", f"[cyan]{getattr(media, 'uploader', '')}[/]")

    media_type = getattr(media, "media_type", None)
    if media_type == MediaType.PLAYLIST:
        grid.add_row("Videos", f"[yellow]{getattr(media, 'item_count', 0)}[/]")
    else:
        duration = getattr(media, "duration", 0)
        grid.add_row("Duration", f"[green]{format_duration(duration)}[/]")

    return grid
