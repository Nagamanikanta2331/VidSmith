"""Queues for playlist and batch orchestration."""

from __future__ import annotations

from collections import deque

from vidsmith.playlist.exceptions import BatchQueueError, PlaylistQueueError
from vidsmith.playlist.models import (
    BatchItem,
    OrchestrationStatus,
    PlaylistItem,
)


class PlaylistQueue:
    """FIFO queue for PlaylistItem objects."""

    def __init__(self) -> None:
        self._order: deque[str] = deque()
        self._items: dict[str, PlaylistItem] = {}
        self._paused = False

    def enqueue(self, item: PlaylistItem) -> str:
        key = self._key(item)
        if key in self._items:
            raise PlaylistQueueError(f"Playlist item is already queued: {key}")
        item.status = OrchestrationStatus.QUEUED
        self._items[key] = item
        self._order.append(key)
        return key

    def dequeue(self) -> PlaylistItem | None:
        if self._paused:
            return None
        while self._order:
            key = self._order.popleft()
            item = self._items.get(key)
            if item is not None and item.status == OrchestrationStatus.QUEUED:
                item.status = OrchestrationStatus.RUNNING
                return item
        return None

    def peek(self) -> PlaylistItem | None:
        if self._paused:
            return None
        for key in self._order:
            item = self._items.get(key)
            if item is not None and item.status == OrchestrationStatus.QUEUED:
                return item
        return None

    def cancel(self, key: str) -> bool:
        item = self._items.get(key)
        if item is None:
            return False
        if item.status in {OrchestrationStatus.COMPLETED, OrchestrationStatus.FAILED}:
            return False
        item.status = OrchestrationStatus.CANCELLED
        return True

    def retry(self, key: str) -> bool:
        item = self._items.get(key)
        if item is None:
            return False
        if item.status != OrchestrationStatus.FAILED:
            raise PlaylistQueueError("Only failed playlist items can be retried.")
        item.status = OrchestrationStatus.QUEUED
        item.error_message = ""
        self._order.append(key)
        return True

    def clear(self) -> None:
        for item in self._items.values():
            if item.status in {OrchestrationStatus.PENDING, OrchestrationStatus.QUEUED}:
                item.status = OrchestrationStatus.CANCELLED
        self._order.clear()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def all_items(self) -> list[PlaylistItem]:
        return list(self._items.values())

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pending_count(self) -> int:
        return sum(1 for item in self._items.values() if item.status == OrchestrationStatus.QUEUED)

    def _key(self, item: PlaylistItem) -> str:
        return f"{item.index}:{item.url}"


class BatchQueue:
    """FIFO queue for BatchItem objects."""

    def __init__(self) -> None:
        self._order: deque[str] = deque()
        self._items: dict[str, BatchItem] = {}
        self._paused = False

    def enqueue(self, item: BatchItem) -> str:
        if item.item_id in self._items:
            raise BatchQueueError(f"Batch item is already queued: {item.item_id}")
        item.status = OrchestrationStatus.QUEUED
        self._items[item.item_id] = item
        self._order.append(item.item_id)
        return item.item_id

    def dequeue(self) -> BatchItem | None:
        if self._paused:
            return None
        while self._order:
            item_id = self._order.popleft()
            item = self._items.get(item_id)
            if item is not None and item.status == OrchestrationStatus.QUEUED:
                item.status = OrchestrationStatus.RUNNING
                return item
        return None

    def peek(self) -> BatchItem | None:
        if self._paused:
            return None
        for item_id in self._order:
            item = self._items.get(item_id)
            if item is not None and item.status == OrchestrationStatus.QUEUED:
                return item
        return None

    def cancel(self, item_id: str) -> bool:
        item = self._items.get(item_id)
        if item is None:
            return False
        if item.status in {OrchestrationStatus.COMPLETED, OrchestrationStatus.FAILED}:
            return False
        item.status = OrchestrationStatus.CANCELLED
        return True

    def retry(self, item_id: str) -> bool:
        item = self._items.get(item_id)
        if item is None:
            return False
        if item.status != OrchestrationStatus.FAILED:
            raise BatchQueueError("Only failed batch items can be retried.")
        item.status = OrchestrationStatus.QUEUED
        item.error_message = ""
        self._order.append(item_id)
        return True

    def retry_failed(self, max_retries: int) -> int:
        retried = 0
        for item in self._items.values():
            if item.status == OrchestrationStatus.FAILED and item.attempts < max_retries:
                item.status = OrchestrationStatus.QUEUED
                item.error_message = ""
                self._order.append(item.item_id)
                retried += 1
        return retried

    def clear(self) -> None:
        for item in self._items.values():
            if item.status in {OrchestrationStatus.PENDING, OrchestrationStatus.QUEUED}:
                item.status = OrchestrationStatus.CANCELLED
        self._order.clear()

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def all_items(self) -> list[BatchItem]:
        return list(self._items.values())

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def pending_count(self) -> int:
        return sum(1 for item in self._items.values() if item.status == OrchestrationStatus.QUEUED)
