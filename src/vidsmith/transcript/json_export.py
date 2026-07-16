"""JSON transcript exporter."""

from __future__ import annotations

import json

from vidsmith.transcript.models import TimestampMode, TranscriptDocument


class JsonExporter:
    """Export transcripts as structured JSON."""

    def export(self, document: TranscriptDocument, timestamp_mode: TimestampMode) -> str:
        entries = []
        for segment in document.segments:
            item: dict[str, object] = {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
            }
            if segment.speaker:
                item["speaker"] = segment.speaker
            entries.append(item)

        payload = {
            "title": document.title,
            "language": document.language,
            "timestamp_mode": timestamp_mode.value,
            "entries": entries,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
