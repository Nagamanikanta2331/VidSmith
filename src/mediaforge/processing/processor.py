"""Processor abstraction for post-download media operations."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mediaforge.processing.models import (
    ProcessingJob,
    ProcessingOperation,
    ProcessingResult,
)


class MediaProcessor(ABC):
    """Abstract media post-processor interface."""

    @abstractmethod
    def process(self, job: ProcessingJob) -> ProcessingResult:
        """Run the requested processing operations."""

    @abstractmethod
    def supports(self, operation: ProcessingOperation) -> bool:
        """Return whether this processor supports an operation."""
