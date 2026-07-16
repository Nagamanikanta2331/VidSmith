"""Transcript parsers for VTT, SRT, and TTML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from vidsmith.transcript.exceptions import (
    TranscriptParseError,
    UnsupportedTranscriptFormatError,
)
from vidsmith.transcript.models import (
    TranscriptDocument,
    TranscriptFormat,
    TranscriptSegment,
)

_TIMESTAMP_LINE = re.compile(r"(?P<start>\S+)\s+-->\s+(?P<end>\S+)")


class TranscriptParser:
    """Parse subtitle files into TranscriptDocument objects."""

    def parse_file(
        self,
        path: Path,
        transcript_format: TranscriptFormat | None = None,
        title: str = "Transcript",
        language: str = "",
    ) -> TranscriptDocument:
        try:
            content = path.read_text(encoding="utf-8-sig")
        except OSError:
            raise TranscriptParseError(f"Unable to read transcript file: {path}") from None

        document = self.parse(
            content, transcript_format or self.infer_format(path), title, language
        )
        return TranscriptDocument(
            segments=document.segments,
            title=document.title,
            language=document.language,
            source_path=path,
            metadata=document.metadata,
        )

    def parse(
        self,
        content: str,
        transcript_format: TranscriptFormat,
        title: str = "Transcript",
        language: str = "",
    ) -> TranscriptDocument:
        try:
            if (
                transcript_format == TranscriptFormat.VTT
                or transcript_format == TranscriptFormat.SRT
            ):
                segments = self._parse_timed_text(content)
            elif transcript_format == TranscriptFormat.TTML:
                segments = self._parse_ttml(content)
            else:
                raise UnsupportedTranscriptFormatError(
                    f"Unsupported transcript format: {transcript_format}"
                )
        except TranscriptParseError:
            raise
        except Exception:
            raise TranscriptParseError("Unable to parse transcript content.") from None

        return TranscriptDocument(segments=segments, title=title, language=language)

    def infer_format(self, path: Path) -> TranscriptFormat:
        suffix = path.suffix.lower().lstrip(".")
        if suffix == "vtt":
            return TranscriptFormat.VTT
        if suffix == "srt":
            return TranscriptFormat.SRT
        if suffix in {"ttml", "xml", "dfxp"}:
            return TranscriptFormat.TTML
        raise UnsupportedTranscriptFormatError(f"Unsupported transcript extension: {path.suffix}")

    def _parse_timed_text(self, content: str) -> list[TranscriptSegment]:
        lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        cues: list[TranscriptSegment] = []
        index = 0

        while index < len(lines):
            line = lines[index].strip()
            if not line or line == "WEBVTT" or line.startswith(("NOTE", "STYLE", "REGION")):
                index += 1
                continue

            match = _TIMESTAMP_LINE.search(line)
            if match is None and index + 1 < len(lines):
                next_line = lines[index + 1].strip()
                match = _TIMESTAMP_LINE.search(next_line)
                if match is not None:
                    index += 1

            if match is None:
                index += 1
                continue

            start = _parse_timestamp(match.group("start"))
            end = _parse_timestamp(match.group("end"))
            index += 1

            text_lines: list[str] = []
            while index < len(lines) and lines[index].strip():
                text_lines.append(lines[index].strip())
                index += 1

            text = "\n".join(text_lines).strip()
            if text:
                cues.append(TranscriptSegment(start=start, end=end, text=text))

        return cues

    def _parse_ttml(self, content: str) -> list[TranscriptSegment]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            raise TranscriptParseError("Unable to parse TTML transcript.") from None

        segments: list[TranscriptSegment] = []
        for element in root.iter():
            if _local_name(element.tag) != "p":
                continue

            start_value = element.attrib.get("begin")
            end_value = element.attrib.get("end")
            duration_value = element.attrib.get("dur")
            if not start_value:
                continue

            start = _parse_timestamp(start_value)
            if end_value:
                end = _parse_timestamp(end_value)
            elif duration_value:
                end = start + _parse_timestamp(duration_value)
            else:
                end = start

            text = " ".join(part.strip() for part in element.itertext() if part.strip())
            if text:
                segments.append(TranscriptSegment(start=start, end=end, text=text))

        return segments


def _parse_timestamp(value: str) -> float:
    clean = value.strip().replace(",", ".")
    clean = clean.split()[0]
    if clean.endswith("ms"):
        return float(clean[:-2]) / 1000
    if clean.endswith("s"):
        return float(clean[:-1])

    parts = clean.split(":")
    try:
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        if len(parts) == 2:
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        return float(clean)
    except ValueError:
        raise TranscriptParseError(f"Invalid timestamp: {value}") from None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
