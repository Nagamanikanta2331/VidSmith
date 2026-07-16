"""Playlist and batch orchestration exceptions."""

from __future__ import annotations

from vidsmith.utils.exceptions import VidSmithError


class PlaylistError(VidSmithError):
    """Base exception for playlist orchestration failures."""


class PlaylistExpansionError(PlaylistError):
    """Raised when a playlist cannot be expanded into item jobs."""


class PlaylistQueueError(PlaylistError):
    """Raised when playlist queue state is invalid."""


class BatchError(VidSmithError):
    """Base exception for batch orchestration failures."""


class BatchQueueError(BatchError):
    """Raised when batch queue state is invalid."""
