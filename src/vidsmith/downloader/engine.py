"""Download engine coordination interfaces."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vidsmith.downloader.job import DownloadJob
from vidsmith.downloader.progress import (
    DownloadProgress,
    DownloadStage,
    ProgressCallback,
)
from vidsmith.downloader.queue import DownloadQueue

if TYPE_CHECKING:
    from vidsmith.providers.base import Provider


class DownloadEngine:
    """Coordinates jobs, providers, and progress callbacks."""

    def __init__(self, provider: Provider, queue: DownloadQueue | None = None) -> None:
        self._provider = provider
        self._queue = queue or DownloadQueue()
        self._callbacks: list[ProgressCallback] = []
        self._progress: dict[str, DownloadProgress] = {}

    def submit(self, job: DownloadJob) -> str:
        job_id = self._queue.enqueue(job)
        self._emit(
            DownloadProgress(
                job_id=job_id,
                stage=DownloadStage.QUEUED,
                message="Job queued.",
            )
        )
        return job_id

    def run_next(self) -> DownloadProgress | None:
        """Reserve the next job for a future provider-backed download."""
        job = self._queue.dequeue()
        if job is None:
            return None

        job.mark_running()
        progress = DownloadProgress(
            job_id=job.job_id,
            stage=DownloadStage.ANALYZING,
            message="Job reserved for provider execution.",
        )
        self._emit(progress)
        return progress

    def cancel(self, job_id: str) -> bool:
        cancelled = self._queue.cancel(job_id)
        if cancelled:
            self._emit(
                DownloadProgress(
                    job_id=job_id,
                    stage=DownloadStage.CANCELLED,
                    message="Job cancelled.",
                )
            )
        return cancelled

    def retry(self, job_id: str) -> bool:
        found = self._queue.retry(job_id)
        if found:
            self._emit(
                DownloadProgress(
                    job_id=job_id,
                    stage=DownloadStage.QUEUED,
                    message="Job queued for retry.",
                )
            )
        return found

    def get_progress(self, job_id: str) -> DownloadProgress | None:
        return self._progress.get(job_id)

    def get_all_progress(self) -> dict[str, DownloadProgress]:
        return dict(self._progress)

    def register_progress_callback(self, callback: ProgressCallback) -> None:
        self._callbacks.append(callback)

    def unregister_progress_callback(self, callback: ProgressCallback) -> bool:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            return False
        return True

    @property
    def provider(self) -> Provider:
        return self._provider

    @property
    def queue(self) -> DownloadQueue:
        return self._queue

    def _emit(self, progress: DownloadProgress) -> None:
        self._progress[progress.job_id] = progress
        for callback in self._callbacks:
            callback(progress)
