"""Plain text transcript exporter and timestamp helpers."""

from __future__ import annotations

from vidsmith.transcript.models import TimestampMode, TranscriptDocument


class TextExporter:
    """Export transcripts as plain text."""

    def export(self, document: TranscriptDocument, timestamp_mode: TimestampMode) -> str:
        lines = [document.title, ""]
        for segment in document.segments:
            timestamp = self._timestamp(segment.start, segment.end, timestamp_mode)
            if timestamp:
                lines.append(timestamp)
            text = f"{segment.speaker}: {segment.text}" if segment.speaker else segment.text
            lines.extend([text, ""])
        return "\n".join(lines).rstrip() + "\n"

    def _timestamp(self, start: float, end: float, mode: TimestampMode) -> str:
        if mode == TimestampMode.NONE:
            return ""
        if mode == TimestampMode.START_END:
            return f"{format_timestamp(start)} - {format_timestamp(end)}"
        return format_timestamp(start)


def format_timestamp(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
