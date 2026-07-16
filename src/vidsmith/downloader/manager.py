"""
DownloadManager — the single public facade over the download subsystem.

This is the only class the rest of the application (CLI dispatcher, future TUI)
should import from the downloader package.  It hides the engine, queue, and
provider and exposes a minimal, stable API.
"""

from __future__ import annotations

from vidsmith.downloader.engine import DownloadEngine
from vidsmith.downloader.job import DownloadJob, JobStatus
from vidsmith.downloader.progress import DownloadProgress, ProgressCallback
from vidsmith.downloader.queue import DownloadQueue


class DownloadManager:
    """Facade that owns one DownloadEngine and exposes a stable public API."""

    def __init__(self, engine: DownloadEngine) -> None:
        self._engine = engine

    # ── submission ────────────────────────────────────────────────────────────

    def submit(self, job: DownloadJob) -> str:
        """Enqueue *job* for download. Returns the job_id."""
        return self._engine.submit(job)

    # ── execution ─────────────────────────────────────────────────────────────

    def run_next(self) -> DownloadProgress | None:
        """Execute the next queued job. Returns terminal progress or None."""
        return self._engine.run_next()

    # ── job control ───────────────────────────────────────────────────────────

    def cancel(self, job_id: str) -> bool:
        """Cancel a PENDING or RUNNING job. Returns True if found."""
        return self._engine.cancel(job_id)

    def retry(self, job_id: str) -> bool:
        """Re-enqueue a FAILED or CANCELLED job. Returns True if found."""
        return self._engine.retry(job_id)

    # ── progress ──────────────────────────────────────────────────────────────

    def get_progress(self, job_id: str) -> DownloadProgress | None:
        """Return the latest progress snapshot for *job_id*, or None."""
        return self._engine.get_progress(job_id)

    def get_all_progress(self) -> dict[str, DownloadProgress]:
        """Return all tracked progress snapshots keyed by job_id."""
        return self._engine.get_all_progress()

    def register_progress_callback(self, callback: ProgressCallback) -> None:
        """Register a callable invoked on every progress update."""
        self._engine.register_progress_callback(callback)

    def unregister_progress_callback(self, callback: ProgressCallback) -> bool:
        """Remove a previously registered callback."""
        return self._engine.unregister_progress_callback(callback)

    # ── job listing ───────────────────────────────────────────────────────────

    def list_jobs(
        self,
        status_filter: JobStatus | None = None,
    ) -> list[DownloadJob]:
        """Return all tracked jobs, optionally filtered by status."""
        jobs = self._engine.queue.all_jobs()
        if status_filter is not None:
            jobs = [j for j in jobs if j.status == status_filter]
        return jobs

    def get_job(self, job_id: str) -> DownloadJob | None:
        """Return a specific job by id, or None if not found."""
        return self._engine.queue.get(job_id)

    def clear_completed(self) -> int:
        """Remove all COMPLETED and CANCELLED jobs from the queue."""
        to_remove = [
            j.job_id
            for j in self._engine.queue.all_jobs()
            if j.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}
        ]
        for job_id in to_remove:
            self._engine.queue.remove(job_id)
        return len(to_remove)

    # ── queue introspection ───────────────────────────────────────────────────

    @property
    def queue_size(self) -> int:
        return self._engine.queue.size

    @property
    def pending_count(self) -> int:
        return self._engine.queue.pending_count

    @property
    def is_idle(self) -> bool:
        return self._engine.queue.is_empty

    # ── factory ───────────────────────────────────────────────────────────────

    @classmethod
    def create(cls, provider: object) -> DownloadManager:
        """
        Convenience factory: wraps provider in an engine with a fresh queue.

        Usage:
            manager = DownloadManager.create(YouTubeProvider(config={}))
        """
        from vidsmith.providers.base import Provider

        if not isinstance(provider, Provider):
            raise TypeError(
                f"provider must be a Provider subclass, got {type(provider).__name__!r}"
            )
        engine = DownloadEngine(provider=provider, queue=DownloadQueue())
        return cls(engine)

    def __repr__(self) -> str:
        return f"DownloadManager(" f"pending={self.pending_count}, " f"total={self.queue_size})"
