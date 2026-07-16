"""Transcript-specific VidSmith exceptions."""

from __future__ import annotations

from vidsmith.utils.exceptions import VidSmithError


class TranscriptError(VidSmithError):
    """Base exception for transcript failures."""


class TranscriptParseError(TranscriptError):
    """Raised when transcript input cannot be parsed."""


class TranscriptExportError(TranscriptError):
    """Raised when transcript output cannot be exported."""


class UnsupportedTranscriptFormatError(TranscriptError):
    """Raised when a transcript format is unsupported."""
