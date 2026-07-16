"""
NumericStep — bounded integer input with unit label.

UX:
  • Shows the prompt with range and default.
  • Empty Enter → accept current/default.
  • p alone     → BACK.
  • c alone     → CANCEL.
"""

from __future__ import annotations

from mediaforge.cli.wizard.base import StepContext, StepSignal, WizardState
from mediaforge.cli.wizard.chrome import render_nav_footer, render_wizard_header
from mediaforge.cli.wizard.steps._base import BaseStep, _SkipPredicate
from mediaforge.utils.console import console


class NumericStep(BaseStep):
    def __init__(
        self,
        key: str,
        title: str,
        prompt_label: str,
        min_value: int,
        max_value: int,
        default: int,
        unit: str = "",
        step: int = 1,
        description: str = "",
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        super().__init__(key, title, skip_when)
        self._prompt_label = prompt_label
        self._min = min_value
        self._max = max_value
        self._default = default
        self._unit = unit
        self._step = step
        self._description = description

    def run(self, ctx: StepContext) -> StepSignal:
        render_wizard_header(ctx)

        current: int = ctx.state.get(self._key, self._default)

        if self._description:
            console.print(f"  [dim]{self._description}[/]\n")

        unit_suffix = f" {self._unit}" if self._unit else ""
        console.print(
            f"  Range: [cyan]{self._min}–{self._max}{unit_suffix}[/]  "
            f"Current: [bold white]{current}{unit_suffix}[/]\n"
        )

        render_nav_footer(is_first=ctx.is_first, confirm=ctx.is_last)
        return self._prompt(ctx.state, current)

    def _prompt(self, state: WizardState, current: int) -> StepSignal:
        unit_suffix = f" {self._unit}" if self._unit else ""
        hint = f"[dim](default {current}{unit_suffix})[/]"

        while True:
            raw = console.input(f"  [bold cyan]{self._prompt_label}[/] {hint}: ").strip()

            if raw == "p":
                return StepSignal.BACK
            if raw == "c":
                return StepSignal.CANCEL
            if raw == "":
                self._commit(state, current)
                return StepSignal.NEXT
            if raw.lstrip("-").isdigit():
                val = int(raw)
                if self._min <= val <= self._max:
                    self._commit(state, val)
                    return StepSignal.NEXT
                console.print(f"  [error]Must be between {self._min} and {self._max}.[/]")
                continue

            console.print("  [error]Enter a whole number.[/]")

    def _commit(self, state: WizardState, value: int) -> None:
        unit_suffix = f" {self._unit}" if self._unit else ""
        state.set(self._key, value)
        state.set(f"__display_{self._key}", f"{value}{unit_suffix}")
