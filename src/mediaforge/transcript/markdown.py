"""Markdown transcript exporter."""

from __future__ import annotations

from mediaforge.transcript.models import TimestampMode, TranscriptDocument
from mediaforge.transcript.text import format_timestamp


class MarkdownExporter:
    """Export transcripts as professional Markdown."""

    def export(self, document: TranscriptDocument, timestamp_mode: TimestampMode) -> str:
        lines = [f"# {document.title}", "", "## Transcript", ""]
        for segment in document.segments:
            timestamp = self._timestamp(segment.start, segment.end, timestamp_mode)
            if timestamp:
                lines.extend([timestamp, ""])
            text = f"**{segment.speaker}:** {segment.text}" if segment.speaker else segment.text
            lines.extend([text, ""])
        return "\n".join(lines).rstrip() + "\n"

    def _timestamp(self, start: float, end: float, mode: TimestampMode) -> str:
        if mode == TimestampMode.NONE:
            return ""
        if mode == TimestampMode.START_END:
            return f"{format_timestamp(start)} - {format_timestamp(end)}"
        return format_timestamp(start)
