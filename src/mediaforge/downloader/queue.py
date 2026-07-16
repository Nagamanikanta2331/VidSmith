"""Simple FIFO queue management for download jobs."""

from __future__ import annotations

from collections import deque

from mediaforge.downloader.job import DownloadJob, JobStatus
from mediaforge.utils.exceptions import JobNotFoundError, QueueError


class DownloadQueue:
    """A small in-memory FIFO queue for DownloadJob instances."""

    def __init__(self) -> None:
        self._order: deque[str] = deque()
        self._jobs: dict[str, DownloadJob] = {}

    def enqueue(self, job: DownloadJob) -> str:
        if job.job_id in self._jobs:
            raise QueueError(f"Job already queued: {job.job_id}")
        self._jobs[job.job_id] = job
        self._order.append(job.job_id)
        return job.job_id

    def dequeue(self) -> DownloadJob | None:
        while self._order:
            job_id = self._order.popleft()
            job = self._jobs.get(job_id)
            if job is not None and job.status == JobStatus.PENDING:
                return job
        return None

    def peek(self) -> DownloadJob | None:
        for job_id in self._order:
            job = self._jobs.get(job_id)
            if job is not None and job.status == JobStatus.PENDING:
                return job
        return None

    def clear(self) -> None:
        for job in self._jobs.values():
            if job.status == JobStatus.PENDING:
                job.mark_cancelled()
        self._order.clear()

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        job.mark_cancelled()
        return True

    def retry(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}:
            raise QueueError(f"Job is not retryable: {job_id}")
        job.reset_for_retry()
        self._order.append(job_id)
        return True

    def remove(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        self._jobs.pop(job_id)
        try:
            self._order.remove(job_id)
        except ValueError:
            pass
        return True

    def get(self, job_id: str) -> DownloadJob | None:
        return self._jobs.get(job_id)

    def get_or_raise(self, job_id: str) -> DownloadJob:
        job = self.get(job_id)
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    def all_jobs(self) -> list[DownloadJob]:
        """Return all tracked jobs in insertion order."""
        return list(self._jobs.values())

    @property
    def size(self) -> int:
        return len(self._jobs)

    @property
    def pending_count(self) -> int:
        return sum(1 for job in self._jobs.values() if job.status == JobStatus.PENDING)

    @property
    def is_empty(self) -> bool:
        return self.pending_count == 0
