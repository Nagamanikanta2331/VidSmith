"""Batch orchestration engine."""

from __future__ import annotations

from vidsmith.downloader.job import DownloadJob
from vidsmith.downloader.manager import DownloadManager
from vidsmith.playlist.engine import PlaylistEngine
from vidsmith.playlist.exceptions import BatchError
from vidsmith.playlist.models import (
    BatchItem,
    BatchJob,
    BatchResult,
    OrchestrationClock,
    OrchestrationStatus,
    PlaylistJob,
    PlaylistProgress,
    PlaylistResult,
    progress_for_items,
)
from vidsmith.playlist.queue import BatchQueue
from vidsmith.providers.metadata import ProviderMediaType
from vidsmith.utils.exceptions import VidSmithError


class BatchEngine:
    """Coordinate a queue of video and playlist jobs without downloading directly."""

    def __init__(
        self,
        download_manager: DownloadManager,
        provider: object | None = None,
        queue: BatchQueue | None = None,
        playlist_engine: PlaylistEngine | None = None,
    ) -> None:
        self.download_manager = download_manager
        self.provider = provider
        self.queue = queue or BatchQueue()
        self.playlist_engine = playlist_engine or PlaylistEngine(download_manager, provider)
        self._clock = OrchestrationClock()

    def submit(self, job: BatchJob) -> BatchResult:
        """Submit every batch item in order."""
        for item in job.items:
            self.queue.enqueue(item)

        queued_job_ids: list[str] = []
        playlist_results: list[PlaylistResult] = []
        errors: list[str] = []

        while True:
            queued_item = self.queue.dequeue()
            if queued_item is None:
                break
            item = queued_item
            item.attempts += 1
            try:
                result = self._submit_item(job, item)
                if isinstance(result, PlaylistResult):
                    playlist_results.append(result)
                    queued_job_ids.extend(result.queued_job_ids)
                else:
                    queued_job_ids.append(result)
                item.status = OrchestrationStatus.QUEUED
            except Exception as exc:
                item.status = OrchestrationStatus.FAILED
                item.error_message = self._error_message(exc)
                errors.append(item.error_message)
                if job.stop_on_first_failure or not job.continue_after_failures:
                    break

        progress = self.progress()
        status = (
            OrchestrationStatus.FAILED
            if errors and not queued_job_ids
            else OrchestrationStatus.COMPLETED
        )
        return BatchResult(
            job_id=job.job_id,
            status=status,
            total_items=progress.total_items,
            completed=progress.completed,
            failed=progress.failed,
            skipped=progress.skipped,
            queued_job_ids=queued_job_ids,
            playlist_results=playlist_results,
            errors=errors,
        )

    def retry_failed(self, job: BatchJob) -> int:
        """Requeue failed batch items that are still below the retry limit."""
        return self.queue.retry_failed(job.max_retries)

    def cancel_queued(self, item_id: str) -> bool:
        return self.queue.cancel(item_id)

    def pause(self) -> None:
        self.queue.pause()

    def resume(self) -> None:
        self.queue.resume()

    def progress(self) -> PlaylistProgress:
        return progress_for_items(self.queue.all_items(), self._clock)

    def _submit_item(self, job: BatchJob, item: BatchItem) -> str | PlaylistResult:
        if item.playlist_job is not None:
            return self.playlist_engine.submit(item.playlist_job)

        if item.download_job is not None:
            return self.download_manager.submit(item.download_job)

        metadata = self._analyze(item.url)
        if getattr(metadata, "media_type", None) == ProviderMediaType.PLAYLIST:
            playlist_job = PlaylistJob(url=item.url, output_dir=job.output_dir)
            return self.playlist_engine.submit(playlist_job)

        download_job = DownloadJob(
            url=item.url,
            media_type=job.media_type,
            output_dir=job.output_dir,
            quality=job.quality,
            video_format=job.video_format,
            audio_format=job.audio_format,
            audio_quality=job.audio_quality,
        )
        return self.download_manager.submit(download_job)

    def _analyze(self, url: str) -> object:
        if self.provider is None or not hasattr(self.provider, "analyze"):
            return object()
        analyze = getattr(self.provider, "analyze")
        if not callable(analyze):
            return object()
        try:
            return analyze(url)
        except Exception as exc:
            raise BatchError(self._error_message(exc)) from None

    def _error_message(self, exc: Exception) -> str:
        if isinstance(exc, (BatchError, VidSmithError)):
            return str(exc)
        return f"Batch orchestration failed: {exc}"
