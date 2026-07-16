"""Transcript engine orchestration."""

from __future__ import annotations

from pathlib import Path

from vidsmith.transcript.cleaner import TranscriptCleaner
from vidsmith.transcript.exceptions import TranscriptError, TranscriptExportError
from vidsmith.transcript.json_export import JsonExporter
from vidsmith.transcript.markdown import MarkdownExporter
from vidsmith.transcript.models import (
    TimestampMode,
    TranscriptDocument,
    TranscriptJob,
    TranscriptOutputFormat,
    TranscriptResult,
)
from vidsmith.transcript.parser import TranscriptParser
from vidsmith.transcript.text import TextExporter


def _format_timestamp(seconds: float, is_srt: bool = False) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    secs_int = int(secs)
    millis = round((secs - float(secs_int)) * 1000)
    if millis >= 1000:
        millis -= 1000
        secs_int += 1
        if secs_int >= 60:
            secs_int -= 60
            minutes += 1
            if minutes >= 60:
                minutes -= 60
                hours += 1
    sep = "," if is_srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs_int:02d}{sep}{millis:03d}"


def _export_srt(document: TranscriptDocument) -> str:
    lines = []
    for i, seg in enumerate(document.segments, 1):
        start_str = _format_timestamp(seg.start, is_srt=True)
        end_str = _format_timestamp(seg.end, is_srt=True)
        lines.append(f"{i}")
        lines.append(f"{start_str} --> {end_str}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


def _export_vtt(document: TranscriptDocument) -> str:
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(document.segments, 1):
        start_str = _format_timestamp(seg.start, is_srt=False)
        end_str = _format_timestamp(seg.end, is_srt=False)
        lines.append(f"{i}")
        lines.append(f"{start_str} --> {end_str}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)


class TranscriptEngine:
    """Convert subtitle files into clean structured transcript documents."""

    def __init__(
        self,
        parser: TranscriptParser | None = None,
        cleaner: TranscriptCleaner | None = None,
        markdown_exporter: MarkdownExporter | None = None,
        text_exporter: TextExporter | None = None,
        json_exporter: JsonExporter | None = None,
    ) -> None:
        self.parser = parser or TranscriptParser()
        self.cleaner = cleaner or TranscriptCleaner()
        self.markdown_exporter = markdown_exporter or MarkdownExporter()
        self.text_exporter = text_exporter or TextExporter()
        self.json_exporter = json_exporter or JsonExporter()

    def parse(
        self, path: Path, title: str = "Transcript", language: str = ""
    ) -> TranscriptDocument:
        document = self.parser.parse_file(path, title=title, language=language)
        return self.cleaner.clean(document)

    def convert(self, job: TranscriptJob) -> TranscriptResult:
        document = self.parser.parse_file(
            job.input_path,
            transcript_format=job.input_format,
            title=job.title,
            language=job.language,
        )
        cleaned = self.cleaner.clean(document)
        output = self.export(cleaned, job.output_format, job.timestamp_mode)
        try:
            job.output_path.parent.mkdir(parents=True, exist_ok=True)
            job.output_path.write_text(output, encoding="utf-8")
        except OSError:
            raise TranscriptExportError(
                f"Unable to write transcript output: {job.output_path}"
            ) from None

        return TranscriptResult(
            output_path=job.output_path,
            output_format=job.output_format,
            segment_count=len(cleaned.segments),
            title=cleaned.title,
        )

    def export(
        self,
        document: TranscriptDocument,
        output_format: TranscriptOutputFormat,
        timestamp_mode: TimestampMode = TimestampMode.START,
    ) -> str:
        try:
            if output_format == TranscriptOutputFormat.MARKDOWN:
                return self.markdown_exporter.export(document, timestamp_mode)
            if output_format == TranscriptOutputFormat.TEXT:
                return self.text_exporter.export(document, timestamp_mode)
            if output_format == TranscriptOutputFormat.JSON:
                return self.json_exporter.export(document, timestamp_mode)
            if output_format == TranscriptOutputFormat.SRT:
                return _export_srt(document)
            if output_format == TranscriptOutputFormat.VTT:
                return _export_vtt(document)
        except TranscriptError:
            raise
        except Exception:
            raise TranscriptExportError("Unable to export transcript document.") from None
        raise TranscriptExportError(f"Unsupported transcript output format: {output_format}")
