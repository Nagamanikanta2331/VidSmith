"""
Core wizard types. Nothing in this module imports from Rich, yt-dlp, or any
MediaForge domain module — it is the pure engine layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Protocol, runtime_checkable

# ── state ─────────────────────────────────────────────────────────────────────


class WizardState:
    """
    Mutable key/value store shared across all steps in a single wizard run.

    Conventions:
      state[key]              – raw value chosen by the user
      state[f"__display_{key}"] – human-readable label (written by each step)
      state["__media__"]      – AnalysisResult, injected by the dispatcher
    """

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(initial or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def all(self) -> dict[str, Any]:
        """Return a shallow copy of all entries (excludes private __ keys)."""
        return {k: v for k, v in self._data.items() if not k.startswith("__")}

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __repr__(self) -> str:
        return f"WizardState({self._data!r})"


# ── signals ───────────────────────────────────────────────────────────────────


class StepSignal(Enum):
    NEXT = auto()
    BACK = auto()
    CANCEL = auto()


# ── context ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StepContext:
    """Immutable snapshot passed to each step's run() call."""

    step_num: int  # 1-based visible position
    total_visible: int  # total non-skipped steps in this run
    wizard_title: str
    step_title: str
    state: WizardState
    is_first: bool
    is_last: bool


# ── protocol ──────────────────────────────────────────────────────────────────


@runtime_checkable
class WizardStep(Protocol):
    """
    Structural protocol. Any class that has these four members is a valid step —
    no inheritance required. This is the primary extension point for future
    AI-powered steps.
    """

    @property
    def title(self) -> str: ...

    @property
    def key(self) -> str: ...

    def run(self, ctx: StepContext) -> StepSignal: ...

    def should_skip(self, state: WizardState) -> bool: ...


# ── engine ────────────────────────────────────────────────────────────────────


@dataclass
class Wizard:
    """
    Navigation engine. Accepts a list of WizardStep instances and orchestrates
    them: renders each step via step.run(), handles NEXT/BACK/CANCEL, and
    skips steps whose should_skip() returns True.

    Returns the completed WizardState on success, None on cancel.
    """

    title: str
    steps: list[WizardStep]

    def run(self, initial: dict[str, Any] | None = None) -> WizardState | None:
        if not self.steps:
            return WizardState(initial)

        state = WizardState(initial)
        cursor = 0

        while 0 <= cursor < len(self.steps):
            step = self.steps[cursor]

            # Auto-advance over steps that should be skipped
            if step.should_skip(state):
                cursor += 1
                continue

            # Recompute visible index list each iteration (skip logic may
            # have changed because of earlier step choices)
            visible = [i for i, s in enumerate(self.steps) if not s.should_skip(state)]

            try:
                pos = visible.index(cursor)
            except ValueError:
                # cursor is on a now-skipped step; advance
                cursor += 1
                continue

            ctx = StepContext(
                step_num=pos + 1,
                total_visible=len(visible),
                wizard_title=self.title,
                step_title=step.title,
                state=state,
                is_first=(pos == 0),
                is_last=(pos == len(visible) - 1),
            )

            signal = step.run(ctx)

            match signal:
                case StepSignal.NEXT:
                    cursor += 1

                case StepSignal.BACK:
                    # Walk backwards, skipping currently-skipped steps
                    cursor -= 1
                    while cursor > 0 and self.steps[cursor].should_skip(state):
                        cursor -= 1

                case StepSignal.CANCEL:
                    return None

        # cursor fell off the end — all steps completed
        return state if cursor >= len(self.steps) else None
