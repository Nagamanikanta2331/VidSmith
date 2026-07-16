from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from mediaforge.cli.summary.model import SummaryModel
from mediaforge.utils.console import console


def _format_bytes(value: int | None) -> str:
    if not value:
        return ""
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if amount < 1024:
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} PB"

def _media_duration(seconds: int | None) -> str:
    if not seconds or seconds <= 0:
        return "Unknown"
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

    rows = [
        ("Video Name", summary.title),
        ("Channel", summary.channel),
        ("File Name", summary.file_name),
        ("Output Folder", summary.output_folder),
        ("Container", summary.container),
        ("Video Quality", summary.video_quality),
        ("Resolution", summary.resolution),
        ("FPS", summary.fps),
        ("HDR", summary.hdr),
        ("Video Codec", summary.video_codec),
        ("Video Bitrate", summary.video_bitrate),
        ("Audio Codec", summary.audio_codec),
        ("Audio Bitrate", summary.audio_bitrate),
        ("Audio Language", summary.audio_language),
        ("File Size", _format_bytes(summary.file_size_bytes) if summary.file_size_bytes else ""),
        ("Duration", _media_duration(summary.duration_seconds)),
        ("Download Time", _elapsed_label(summary.download_seconds)),
    ]

    for label, value in rows:
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
