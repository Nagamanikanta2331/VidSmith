"""Transcript cleaning and normalization."""

from __future__ import annotations

import html
import re

from vidsmith.transcript.models import TranscriptDocument, TranscriptSegment

_WEBVTT_TAG = re.compile(r"</?(?:c|v|lang|ruby|rt)(?:\.[^>\s]+)?(?:\s+[^>]*)?>")
_HTML_TAG = re.compile(r"<[^>]+>")
_SPEAKER = re.compile(r"^\s*(?P<speaker>[A-Z][\w .'-]{0,40}):\s+(?P<text>.+)$")


class TranscriptCleaner:
    """Clean parsed transcript segments without changing their timing."""

    def clean(self, document: TranscriptDocument) -> TranscriptDocument:
        cleaned_segments: list[TranscriptSegment] = []
        previous_text = ""
        seen_exact: set[tuple[float, float, str]] = set()

        for segment in document.segments:
            text = self.clean_text(segment.text)
            if not text:
                continue

            speaker = segment.speaker
            match = _SPEAKER.match(text)
            if match is not None:
                speaker = speaker or match.group("speaker").strip()
                text = match.group("text").strip()

            normalized_text = text.lower()
            exact_key = (round(segment.start, 3), round(segment.end, 3), normalized_text)
            if exact_key in seen_exact:
                continue
            if normalized_text == previous_text:
                continue

            cleaned_segments.append(
                TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=text,
                    speaker=speaker,
                )
            )
            seen_exact.add(exact_key)
            previous_text = normalized_text

        return TranscriptDocument(
            segments=cleaned_segments,
            title=document.title,
            language=document.language,
            source_path=document.source_path,
            metadata=document.metadata,
        )

    def clean_text(self, value: str) -> str:
        text = html.unescape(value)
        speaker = self._extract_vtt_speaker(text)
        text = _WEBVTT_TAG.sub("", text)
        text = _HTML_TAG.sub("", text)
        text = text.replace("\r", "\n")
        lines = [self._normalize_inline(line) for line in text.split("\n")]
        lines = self._dedupe_consecutive_lines(lines)
        text = " ".join(line for line in lines if line)
        text = self._normalize_inline(text)
        if speaker and not _SPEAKER.match(text):
            return f"{speaker}: {text}"
        return text

    def _normalize_inline(self, value: str) -> str:
        text = re.sub(r"\s+", " ", value).strip()
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        text = re.sub(r"([([{])\s+", r"\1", text)
        text = re.sub(r"\s+([])}])", r"\1", text)
        return text

    def _dedupe_consecutive_lines(self, lines: list[str]) -> list[str]:
        result: list[str] = []
        previous = ""
        for line in lines:
            if not line:
                continue
            if line.lower() == previous.lower():
                continue
            result.append(line)
            previous = line
        return result

    def _extract_vtt_speaker(self, value: str) -> str:
        match = re.search(r"<v(?:\.[^>\s]+)?\s+([^>]+)>", value)
        if match is None:
            return ""
        return match.group(1).strip()
