"""
ToggleStep — boolean yes/no prompt.

UX:
  • Displays [Y/n] or [y/N] depending on the default.
  • y / yes / Enter (when default=True) → True.
  • n / no  / Enter (when default=False) → False.
  • p alone → BACK.
  • c alone → CANCEL.
"""

from __future__ import annotations

from mediaforge.cli.wizard.base import StepContext, StepSignal, WizardState
from mediaforge.cli.wizard.chrome import render_nav_footer, render_wizard_header
from mediaforge.cli.wizard.steps._base import BaseStep, _SkipPredicate
from mediaforge.utils.console import console


class ToggleStep(BaseStep):
    def __init__(
        self,
        key: str,
        title: str,
        prompt_label: str,
        default: bool = True,
        description: str = "",
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        super().__init__(key, title, skip_when)
        self._prompt_label = prompt_label
        self._default = default
        self._description = description

    def run(self, ctx: StepContext) -> StepSignal:
        render_wizard_header(ctx)

        current: bool = ctx.state.get(self._key, self._default)

        if self._description:
            console.print(f"  [dim]{self._description}[/]\n")

        yn = "[bold cyan]Y[/][dim]/n[/]" if current else "[dim]y/[/][bold cyan]N[/]"
        console.print(f"  {self._prompt_label}  {yn}\n")

        render_nav_footer(is_first=ctx.is_first, confirm=ctx.is_last)
        return self._prompt(ctx.state, current)

    def _prompt(self, state: WizardState, current: bool) -> StepSignal:
        while True:
            raw = console.input("  [bold cyan]›[/] ").strip().lower()

            if raw == "p":
                return StepSignal.BACK
            if raw == "c":
                return StepSignal.CANCEL
            if raw in {"y", "yes"}:
                self._commit(state, True)
                return StepSignal.NEXT
            if raw in {"n", "no"}:
                self._commit(state, False)
                return StepSignal.NEXT
            if raw == "":
                self._commit(state, current)
                return StepSignal.NEXT

            console.print("  [error]Enter y or n.[/]")

    def _commit(self, state: WizardState, value: bool) -> None:
        state.set(self._key, value)
        state.set(f"__display_{self._key}", "Yes" if value else "No")
