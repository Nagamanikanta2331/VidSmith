"""
TextInputStep — free-text / path input.

UX:
  • Shows the prompt with the default value in brackets.
  • Empty Enter → accept default.
  • p alone     → BACK.
  • c alone     → CANCEL.
  • Anything else → validate (optional) and accept.
"""

from __future__ import annotations

from collections.abc import Callable

from mediaforge.cli.wizard.base import StepContext, StepSignal, WizardState
from mediaforge.cli.wizard.chrome import render_nav_footer, render_wizard_header
from mediaforge.cli.wizard.steps._base import BaseStep, _SkipPredicate
from mediaforge.utils.console import console

_Validator = Callable[[str], str | None]  # returns error msg or None


class TextInputStep(BaseStep):
    def __init__(
        self,
        key: str,
        title: str,
        prompt_label: str,
        default: str = "",
        validator: _Validator | None = None,
        placeholder: str = "",
        description: str = "",
        allow_empty: bool = False,
        skip_when: _SkipPredicate | None = None,
    ) -> None:
        super().__init__(key, title, skip_when)
        self._prompt_label = prompt_label
        self._default = default
        self._validator = validator
        self._placeholder = placeholder
        self._description = description
        self._allow_empty = allow_empty

    def run(self, ctx: StepContext) -> StepSignal:
        render_wizard_header(ctx)

        current = ctx.state.get(self._key, self._default)

        if self._description:
            console.print(f"  [dim]{self._description}[/]\n")

        render_nav_footer(is_first=ctx.is_first, confirm=ctx.is_last)
        return self._prompt(ctx.state, str(current))

    def _prompt(self, state: WizardState, current: str) -> StepSignal:
        default_hint = f" [dim][{current}][/]" if current else ""
        label = f"  [bold cyan]{self._prompt_label}[/]{default_hint}: "

        while True:
            raw = console.input(label).strip()

            if raw == "p":
                return StepSignal.BACK
            if raw == "c":
                return StepSignal.CANCEL

            value = raw if raw else current

            if not value:
                if not self._allow_empty:
                    console.print("  [error]A value is required.[/]")
                    continue
                state.set(self._key, "")
                state.set(f"__display_{self._key}", "(not set)")
                return StepSignal.NEXT

            if self._validator:
                error = self._validator(value)
                if error:
                    console.print(f"  [error]{error}[/]")
                    continue

            state.set(self._key, value)
            state.set(f"__display_{self._key}", value)
            return StepSignal.NEXT
