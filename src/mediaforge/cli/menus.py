"""
Type-specific menu renderers and interactive selectors.
Each function receives an AnalysisResult and returns the user's chosen action
as a string key, or None when the user quits.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from mediaforge.cli.output import format_duration, format_views, print_rule
from mediaforge.models.media import AnalysisResult
from mediaforge.utils.console import console

# ── shared action keys ────────────────────────────────────────────────────────
ACTION_BACK = "back"
ACTION_QUIT = "quit"

# ── video / shorts actions ────────────────────────────────────────────────────
VIDEO_ACTIONS: list[tuple[str, str, str]] = [
    ("1", "⭐ Best Download (Recommended)", "best_download"),
    ("2", "Custom Video Download", "video"),
    ("3", "Download Audio Only", "audio"),
    ("4", "Download Subtitles Only", "subtitles"),
    ("5", "Download Thumbnail Only", "thumbnail"),
    ("6", "Extract Transcript", "transcript"),
    ("7", "View Metadata", "metadata"),
    ("s", "Settings", "settings"),
    ("b", "<< Back", ACTION_BACK),
    ("q", "Quit", ACTION_QUIT),
]

# ── playlist actions ──────────────────────────────────────────────────────────
PLAYLIST_ACTIONS: list[tuple[str, str, str]] = [
    ("1", "⭐ Best Download (Recommended)", "best_playlist_download"),
    ("2", "Custom Playlist Download", "playlist_video"),
    ("3", "Download All Audio", "playlist_audio"),
    ("4", "Download All Subtitles", "playlist_subtitles"),
    ("5", "Download All Thumbnails", "playlist_thumbnails"),
    ("6", "Select Specific Items", "playlist_select"),
    ("7", "View Playlist Metadata", "metadata"),
    ("s", "Settings", "settings"),
    ("b", "<< Back", ACTION_BACK),
    ("q", "Quit", ACTION_QUIT),
]


# ── helpers ───────────────────────────────────────────────────────────────────


def _media_type_badge(result: AnalysisResult) -> Text:
    from mediaforge.models.media import MediaType

    badges = {
        MediaType.VIDEO: Text(" VIDEO ", style="bold white on blue"),
        MediaType.SHORTS: Text(" SHORTS ", style="bold white on magenta"),
        MediaType.PLAYLIST: Text(" PLAYLIST ", style="bold white on dark_orange"),
    }
    return badges.get(result.media_type, Text(" UNKNOWN ", style="dim"))


def _render_info_panel(result: AnalysisResult) -> Panel:
    from mediaforge.models.media import MediaType

    badge = _media_type_badge(result)

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", min_width=12)
    grid.add_column()

    grid.add_row("Title", f"[bold white]{result.title}[/]")
    grid.add_row("Channel", f"[cyan]{result.uploader}[/]")

    if result.media_type == MediaType.PLAYLIST:
        grid.add_row("Videos", f"[yellow]{result.item_count}[/]")
    else:
        grid.add_row("Duration", f"[green]{format_duration(result.duration)}[/]")
        if result.view_count:
            grid.add_row("Views", f"[yellow]{format_views(result.view_count)}[/]")

    header = Text()
    header.append_text(badge)
    header.append("  ")
    header.append(result.url, style="dim underline")

    from rich.console import Group

    content = Group(header, Text(""), grid)

    return Panel(content, border_style="cyan", padding=(1, 2))


def _render_action_table(actions: list[tuple[str, str, str]]) -> Table:
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        expand=False,
    )
    table.add_column(style="bold cyan", min_width=4)
    table.add_column(style="white")

    for key, label, action in actions:
        if key in ("b", "q"):
            table.add_row(f"[dim]{key}[/]", f"[dim]{label}[/]")
        elif action in ("best_download", "best_playlist_download"):
            table.add_row(key, f"[bold yellow]{label}[/]")
        else:
            table.add_row(key, label)

    return table


def _prompt_choice(actions: list[tuple[str, str, str]]) -> str:
    valid = {k: action for k, _, action in actions}
    keys = "/".join(k for k, _, _ in actions)

    while True:
        raw = Prompt.ask(f"\n  [bold cyan]Choose[/] [dim]({keys})[/]")
        choice = raw.strip().lower()
        if choice in valid:
            return valid[choice]
        console.print(f"  [error]Invalid choice: {raw!r}[/]")


# ── public menu functions ─────────────────────────────────────────────────────


def show_video_menu(result: AnalysisResult) -> str | None:
    console.clear()
    console.print()
    console.print(_render_info_panel(result))
    print_rule("Options")
    console.print(_render_action_table(VIDEO_ACTIONS))

    action = _prompt_choice(VIDEO_ACTIONS)
    return None if action == ACTION_QUIT else action


def show_playlist_menu(result: AnalysisResult) -> str | None:
    console.clear()
    console.print()
    console.print(_render_info_panel(result))

    if result.items:
        print_rule("Playlist Contents")
        _render_playlist_items(result)

    print_rule("Options")
    console.print(_render_action_table(PLAYLIST_ACTIONS))

    action = _prompt_choice(PLAYLIST_ACTIONS)
    return None if action == ACTION_QUIT else action


def _render_playlist_items(result: AnalysisResult) -> None:
    MAX_SHOWN = 10
    items = result.items[:MAX_SHOWN]

    table = Table(
        show_header=True,
        header_style="bold dim",
        box=None,
        padding=(0, 2),
        expand=True,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Title", style="white", no_wrap=False)
    table.add_column("Duration", style="green", justify="right", width=10)

    for i, item in enumerate(items, 1):
        table.add_row(
            str(i),
            item.title or "Unknown",
            format_duration(item.duration),
        )

    remaining = result.item_count - MAX_SHOWN
    console.print(table)
    if remaining > 0:
        console.print(f"  [dim]… and {remaining} more[/]\n")
    else:
        console.print()
