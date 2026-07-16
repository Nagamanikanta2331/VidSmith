"""
MultiSelectStep — checkbox-style multiple selection.

UX:
  • Items rendered with [x] / [ ] indicators.
  • Typing a number toggles that item's selection.
  • Empty Enter confirms the current selection (if it meets min_selections).
  • p alone → BACK.
  • c alone → CANCEL.
"""

from __future__ import annotations

from collections.abc import Callable

from rich.table import Table

from vidsmith.cli.wizard.base import StepContext, StepSignal, WizardState
from vidsmith.cli.wizard.chrome import render_nav_footer, render_wizard_header
from vidsmith.cli.wizard.steps._base import BaseStep, _SkipPredicate
from vidsmith.cli.wizard.steps.choice import Choice
from vidsmith.utils.console import console


class MultiSelectStep(BaseStep):
    def __init__(
        self,
        key: str,
        title: str,
        choices: list[Choice] | Callable[[WizardState], list[Choice]],
        min_selections: int = 1,
        max_selections: int | None = None,
        default_indices: list[int] | None = None,
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        super().__init__(key, title, skip_when)
        self._choices_input = choices
        self._choices: list[Choice] = []
        self._min = min_selections
        self._max_selections = max_selections
        self._default_indices_input = default_indices

    def run(self, ctx: StepContext) -> StepSignal:
        if callable(self._choices_input):
            self._choices = self._choices_input(ctx.state)
        else:
            self._choices = self._choices_input

        self._max = self._max_selections if self._max_selections is not None else len(self._choices)

        if self._default_indices_input is not None:
            default_indices = set(self._default_indices_input)
        else:
            default_indices = {0} if self._choices else set()

        # Restore previous selection if available, else use defaults
        stored: list | None = ctx.state.get(self._key)
        if stored is not None:
            selected: set[int] = {i for i, c in enumerate(self._choices) if c.value in stored}
        else:
            selected = set(default_indices)

        while True:
            render_wizard_header(ctx)
            self._render_choices(selected)
            count = len(selected)
            console.print(f"  [dim]Toggle by number · {count} selected" f" (min {self._min})[/]\n")
            render_nav_footer(is_first=ctx.is_first, confirm=ctx.is_last)

            raw = console.input("  [bold cyan]›[/] ").strip().lower()

            if raw == "p":
                return StepSignal.BACK
            if raw == "c":
                return StepSignal.CANCEL
            if raw == "":
                if count < self._min:
                    console.print(f"  [error]Select at least {self._min} item(s).[/]")
                    continue
                self._commit(ctx.state, selected)
                return StepSignal.NEXT
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(self._choices):
                    if idx in selected:
                        selected.discard(idx)
                    elif len(selected) < self._max:
                        selected.add(idx)
                    else:
                        console.print(f"  [error]Maximum {self._max} selections allowed.[/]")
                continue

            console.print(f"  [error]Enter a number between 1 and {len(self._choices)}.[/]")

    def _render_choices(self, selected: set[int]) -> None:
        table = Table(show_header=False, box=None, padding=(0, 2), expand=False)
        table.add_column(style="bold cyan", width=5)  # checkbox
        table.add_column(style="bold cyan", width=3)  # number
        table.add_column()  # label
        table.add_column(style="dim")  # description

        for i, choice in enumerate(self._choices):
            box = "[bold cyan][x][/]" if i in selected else "[dim][ ][/]"
            num = f"{i + 1}."
            label = f"[bold white]{choice.label}[/]" if i in selected else choice.label
            table.add_row(box, num, label, choice.description)

        console.print(table)

    def _commit(self, state: WizardState, selected: set[int]) -> None:
        values = [self._choices[i].value for i in sorted(selected)]
        labels = [self._choices[i].label for i in sorted(selected)]
        state.set(self._key, values)
        state.set(f"__display_{self._key}", ", ".join(labels))
