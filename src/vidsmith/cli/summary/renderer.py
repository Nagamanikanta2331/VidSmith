from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from vidsmith.cli.summary.model import SummaryModel
from vidsmith.utils.console import console


def _format_bytes(value: int | None) -> str:
    if not value:
        return ""
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} PB"


def _media_duration(seconds: int | float | str | None) -> str:
    if not seconds:
        return "Unknown"
    try:
        seconds = float(seconds)
    except (ValueError, TypeError):
        return "Unknown"
    if seconds <= 0:
        return "Unknown"
    seconds = round(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _elapsed_label(seconds: float | None) -> str:
    if seconds is None:
        return ""
    rounded = max(0, round(seconds))
    if rounded < 60:
        return f"{rounded} seconds"
    return _media_duration(rounded)


def render_summary(title: str, summary: SummaryModel) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim", no_wrap=True)
    table.add_column(style="white")

    for label, value in summary.rows:
        if value and str(value) != "Unknown":
            table.add_row(label, str(value))

    # Features
    if summary.features or summary.subtitles:
        table.add_row("", "")
        for label, value in summary.features:
            table.add_row(label, value)
        for label, value in summary.subtitles:
            table.add_row(f"{label} Subtitle", value)

    console.print()
    console.print(
        Panel(
            table,
            title=f"[bold green] ✓ {title} [/]",
            border_style="green",
            padding=(1, 2),
        )
    )
    Prompt.ask("\n  [dim]Press Enter to continue[/]", default="")
