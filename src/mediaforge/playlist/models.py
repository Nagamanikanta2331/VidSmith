"""Models for playlist and batch orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from pathlib import Path

from mediaforge.downloader.job import DownloadJob, DownloadMediaType, JobStatus


class OrchestrationStatus(str, Enum):
    """Status for playlist and batch orchestration items."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class PlaylistSelectionMode(str, Enum):
    """How playlist items should be selected."""

    ALL = "all"
    SELECTED = "selected"
    RANGE = "range"


@dataclass(slots=True)
class PlaylistItem:
    """One item inside a playlist orchestration."""

    url: str
    index: int
    title: str = ""
    available: bool = True
    selected: bool = True
    download_job: DownloadJob | None = None
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    error_message: str = ""


@dataclass(slots=True)
class PlaylistJob:
    """A request to orchestrate multiple DownloadJobs from one playlist."""

    url: str
    output_dir: Path
    items: list[PlaylistItem] = field(default_factory=list)
    download_template: DownloadJob | None = None
    selection_mode: PlaylistSelectionMode = PlaylistSelectionMode.ALL
    selected_indices: set[int] = field(default_factory=set)
    range_start: int | None = None
    range_end: int | None = None
    skip_unavailable: bool = True
    continue_after_failures: bool = True
    stop_on_first_failure: bool = False
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def create_download_job(self, item: PlaylistItem) -> DownloadJob:
        """Create or return the DownloadJob for a playlist item."""
        if item.download_job is not None:
            return item.download_job
        if self.download_template is None:
            return DownloadJob(
                url=item.url,
                media_type=DownloadMediaType.VIDEO,
                output_dir=self.output_dir,
                output_template="%(playlist_index)s - %(title)s.%(ext)s",
            )
        return replace(
            self.download_template,
            url=item.url,
            job_id=str(uuid.uuid4()),
            status=JobStatus.PENDING,
            error_message="",
        )


@dataclass(slots=True)
class BatchItem:
    """One URL or playlist request in a batch orchestration."""

    url: str
    download_job: DownloadJob | None = None
    playlist_job: PlaylistJob | None = None
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    attempts: int = 0
    error_message: str = ""
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(slots=True)
class BatchJob:
    """A request to orchestrate multiple URLs."""

    items: list[BatchItem]
    output_dir: Path = Path(".")
    media_type: DownloadMediaType = DownloadMediaType.VIDEO
    quality: str = "best"
    video_format: str = "mp4"
    audio_format: str = "mp3"
    audio_quality: str = "192k"
    preserve_order: bool = True
    continue_after_failures: bool = True
    stop_on_first_failure: bool = False
    max_retries: int = 3
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True, slots=True)
class PlaylistProgress:
    """Aggregate progress for playlist or batch orchestration."""

    total_items: int
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    remaining: int = 0
    overall_percentage: float = 0.0
    current_active_item: str = ""
    estimated_remaining_time: str = ""


@dataclass(frozen=True, slots=True)
class PlaylistResult:
    """Result returned by PlaylistEngine."""

    job_id: str
    status: OrchestrationStatus
    total_items: int
    completed: int
    failed: int
    skipped: int
    queued_job_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BatchResult:
    """Result returned by BatchEngine."""

    job_id: str
    status: OrchestrationStatus
    total_items: int
    completed: int
    failed: int
    skipped: int
    queued_job_ids: list[str] = field(default_factory=list)
    playlist_results: list[PlaylistResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class OrchestrationClock:
    """Simple elapsed-time tracker used for estimates."""

    started_at: datetime = field(default_factory=datetime.now)

    def estimate_remaining(self, completed: int, remaining: int) -> str:
        if completed <= 0 or remaining <= 0:
            return ""
        elapsed = (datetime.now() - self.started_at).total_seconds()
        seconds = int((elapsed / completed) * remaining)
        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {secs}s"
        return f"{secs}s"


def progress_for_items(items: list, clock: OrchestrationClock) -> PlaylistProgress:
    """Compute aggregate progress across a list of PlaylistItem or BatchItem objects."""
    total = len(items)
    completed = sum(1 for item in items if item.status == OrchestrationStatus.COMPLETED)
    failed = sum(1 for item in items if item.status == OrchestrationStatus.FAILED)
    skipped = sum(1 for item in items if item.status == OrchestrationStatus.SKIPPED)
    terminal = completed + failed + skipped
    remaining = max(0, total - terminal)
    current = next(
        (
            getattr(item, "title", "") or getattr(item, "url", "")
            for item in items
            if item.status == OrchestrationStatus.RUNNING
        ),
        "",
    )
    percentage = (terminal / total * 100) if total else 0.0
    return PlaylistProgress(
        total_items=total,
        completed=completed,
        failed=failed,
        skipped=skipped,
        remaining=remaining,
        overall_percentage=percentage,
        current_active_item=current,
        estimated_remaining_time=clock.estimate_remaining(completed, remaining),
    )
