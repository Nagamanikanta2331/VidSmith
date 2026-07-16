"""Playlist orchestration engine."""

from __future__ import annotations

from vidsmith.downloader.manager import DownloadManager
from vidsmith.playlist.exceptions import PlaylistError, PlaylistExpansionError
from vidsmith.playlist.models import (
    OrchestrationClock,
    OrchestrationStatus,
    PlaylistItem,
    PlaylistJob,
    PlaylistProgress,
    PlaylistResult,
    PlaylistSelectionMode,
    progress_for_items,
)
from vidsmith.playlist.queue import PlaylistQueue
from vidsmith.providers.metadata import ProviderMediaType
from vidsmith.utils.exceptions import VidSmithError


class PlaylistEngine:
    """Coordinate DownloadJobs for a playlist without downloading directly."""

    def __init__(
        self,
        download_manager: DownloadManager,
        provider: object | None = None,
        queue: PlaylistQueue | None = None,
    ) -> None:
        self.download_manager = download_manager
        self.provider = provider
        self.queue = queue or PlaylistQueue()
        self._clock = OrchestrationClock()

    def submit(self, job: PlaylistJob) -> PlaylistResult:
        """Select playlist items and submit their DownloadJobs to the manager."""
        items = self._expand_items(job)
        selected_items = self._select_items(job, items)
        queued_job_ids: list[str] = []
        errors: list[str] = []

        for item in selected_items:
            if not item.available and job.skip_unavailable:
                item.status = OrchestrationStatus.SKIPPED
                continue

            try:
                self.queue.enqueue(item)
                queued_item = self.queue.dequeue()
                if queued_item is None:
                    continue
                download_job = job.create_download_job(queued_item)
                queued_job_ids.append(self.download_manager.submit(download_job))
                queued_item.status = OrchestrationStatus.QUEUED
            except Exception as exc:
                item.status = OrchestrationStatus.FAILED
                item.error_message = str(exc)
                errors.append(self._error_message(exc))
                if job.stop_on_first_failure or not job.continue_after_failures:
                    break

        progress = self.progress(selected_items)
        status = (
            OrchestrationStatus.FAILED
            if errors and not queued_job_ids
            else OrchestrationStatus.COMPLETED
        )
        return PlaylistResult(
            job_id=job.job_id,
            status=status,
            total_items=progress.total_items,
            completed=progress.completed,
            failed=progress.failed,
            skipped=progress.skipped,
            queued_job_ids=queued_job_ids,
            errors=errors,
        )

    def progress(self, items: list[PlaylistItem] | None = None) -> PlaylistProgress:
        """Return aggregate playlist progress."""
        tracked = items or self.queue.all_items()
        return progress_for_items(tracked, self._clock)

    def pause(self) -> None:
        self.queue.pause()

    def resume(self) -> None:
        self.queue.resume()

    def cancel_queued(self, key: str) -> bool:
        return self.queue.cancel(key)

    def retry(self, key: str) -> bool:
        return self.queue.retry(key)

    def _expand_items(self, job: PlaylistJob) -> list[PlaylistItem]:
        if job.items:
            return list(job.items)

        metadata = self._analyze(job.url)
        entries = getattr(metadata, "items", None) or getattr(metadata, "entries", None)
        if entries:
            return self._items_from_entries(entries)

        media_type = getattr(metadata, "media_type", None)
        if media_type == ProviderMediaType.PLAYLIST:
            count = getattr(metadata, "playlist_count", None)
            raise PlaylistExpansionError(
                f"Provider reported a playlist with {count or 'unknown'} items but did not expose item URLs."
            )

        return [PlaylistItem(url=job.url, index=1, title=getattr(metadata, "title", ""))]

    def _select_items(self, job: PlaylistJob, items: list[PlaylistItem]) -> list[PlaylistItem]:
        if job.selection_mode == PlaylistSelectionMode.SELECTED:
            if job.selected_indices:
                return [item for item in items if item.index in job.selected_indices]
            return [item for item in items if item.index in job.selected_indices or item.selected]
        if job.selection_mode == PlaylistSelectionMode.RANGE:
            start = job.range_start or 1
            end = job.range_end or len(items)
            return [item for item in items if start <= item.index <= end]
        return list(items)

    def _analyze(self, url: str) -> object:
        if self.provider is None or not hasattr(self.provider, "analyze"):
            raise PlaylistExpansionError(
                "A provider with analyze(url) is required to expand playlist URLs."
            )
        analyze = getattr(self.provider, "analyze")
        if not callable(analyze):
            raise PlaylistExpansionError("Provider analyze attribute is not callable.")
        try:
            return analyze(url)
        except Exception as exc:
            raise PlaylistExpansionError(self._error_message(exc)) from None

    def _items_from_entries(self, entries: object) -> list[PlaylistItem]:
        items: list[PlaylistItem] = []
        if not isinstance(entries, list):
            raise PlaylistExpansionError("Provider playlist entries must be a list.")
        for index, entry in enumerate(entries, start=1):
            if isinstance(entry, PlaylistItem):
                items.append(entry)
                continue
            if isinstance(entry, dict):
                url = str(entry.get("url") or entry.get("webpage_url") or "")
                title = str(entry.get("title", ""))
                available = bool(entry.get("available", True))
            else:
                url = getattr(entry, "url", "") or getattr(entry, "webpage_url", "")
                title = getattr(entry, "title", "")
                available = getattr(entry, "available", True)
            if not url:
                available = False
            items.append(PlaylistItem(url=url, index=index, title=title, available=available))
        return items

    def _error_message(self, exc: Exception) -> str:
        if isinstance(exc, (PlaylistError, VidSmithError)):
            return str(exc)
        return f"Playlist orchestration failed: {exc}"
