"""
ChoiceStep — single-selection radio list.

UX:
  • Items are numbered 1..N.
  • Current selection (from prior visit or default) is marked with ▶.
  • Type a number + Enter  → select that item and advance.
  • Empty Enter            → accept current/default and advance.
  • p                      → BACK.
  • c                      → CANCEL.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from rich.table import Table

from vidsmith.cli.wizard.base import StepContext, StepSignal, WizardState
from vidsmith.cli.wizard.chrome import render_nav_footer, render_wizard_header
from vidsmith.cli.wizard.steps._base import BaseStep, _SkipPredicate
from vidsmith.utils.console import console


@dataclass
class Choice:
    label: str
    value: Any
    description: str = ""


class ChoiceStep(BaseStep):
    def __init__(
        self,
        key: str,
        title: str,
        choices: list[Choice] | Callable[[WizardState], list[Choice]],
        default_index: int | Callable[[list[Choice]], int] = 0,
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        super().__init__(key, title, skip_when)
        self._choices_input = choices
        self._choices: list[Choice] = []
        self._default_index = default_index

    def run(self, ctx: StepContext) -> StepSignal:
        if callable(self._choices_input):
            self._choices = self._choices_input(ctx.state)
        else:
            self._choices = self._choices_input

        render_wizard_header(ctx)

        # Determine active index (use previously stored value if available)
        current_index = self._resolve_current(ctx.state)

        self._render_choices(current_index)
        render_nav_footer(is_first=ctx.is_first, confirm=ctx.is_last)

        return self._prompt(ctx.state, current_index)

    # ── internal ──────────────────────────────────────────────────────────────

    def _resolve_current(self, state: WizardState) -> int:
        stored = state.get(self._key)
        if stored is not None:
            for i, c in enumerate(self._choices):
                if c.value == stored:
                    return i
        default = self._default_index
        if callable(default):
            default = default(self._choices)
        if 0 <= default < len(self._choices):
            return default
        return 0

    def _render_choices(self, current_index: int) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
        table.add_column(style="dim", width=2)  # marker
        table.add_column(style="bold cyan", width=3)  # number
        table.add_column()  # label
        table.add_column(style="dim")  # description

        for i, choice in enumerate(self._choices):
            marker = "[bold cyan]>[/]" if i == current_index else " "
            num = f"{i + 1}."
            label = f"[bold white]{choice.label}[/]" if i == current_index else choice.label
            table.add_row(marker, num, label, choice.description)

        console.print(table)

    def _prompt(self, state: WizardState, current_index: int) -> StepSignal:
        default_label = self._choices[current_index].label
        hint = f"[dim](1–{len(self._choices)}, or Enter for[/] [cyan]{default_label}[/][dim])[/]"

        while True:
            raw = console.input(f"  [bold cyan]›[/] {hint} ").strip().lower()

            if raw == "p":
                return StepSignal.BACK
            if raw == "c":
                return StepSignal.CANCEL
            if raw == "":
                self._commit(state, current_index)
                return StepSignal.NEXT
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(self._choices):
                    self._commit(state, idx)
                    return StepSignal.NEXT

            console.print(f"  [error]Enter a number between 1 and {len(self._choices)}.[/]")

    def _commit(self, state: WizardState, index: int) -> None:
        choice = self._choices[index]
        state.set(self._key, choice.value)
        state.set(f"__display_{self._key}", choice.label)
