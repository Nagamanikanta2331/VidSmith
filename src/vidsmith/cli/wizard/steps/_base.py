"""BaseStep mixin — shared constructor and should_skip logic."""

from __future__ import annotations

from collections.abc import Callable

from vidsmith.cli.wizard.base import WizardState

_SkipPredicate = Callable[[WizardState], bool]


class BaseStep:
    """
    Mixin that provides the standard __init__ and should_skip implementation.
    All concrete steps inherit from this so they avoid repeating boilerplate.
    """

    def __init__(
        self,
        key: str,
        title: str,
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        self._key = key
        self._title = title
        self._skip_when = skip_when

    @property
    def key(self) -> str:
        return self._key

    @property
    def title(self) -> str:
        return self._title

    def should_skip(self, state: WizardState) -> bool:
        if self._skip_when is not None:
            return self._skip_when(state)
        return False
