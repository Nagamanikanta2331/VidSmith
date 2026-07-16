"""
ConfirmationStep — final review page shown as the last step of every wizard.

Reads __display_{key} values written by previous steps to build the summary
table. Falls back to str(raw_value) for keys without a display counterpart.

UX:
  • Enter / y  → NEXT  (commit)
  • p          → BACK
  • c          → CANCEL
"""

from __future__ import annotations

from mediaforge.cli.wizard.base import StepContext, StepSignal, WizardState
from mediaforge.cli.wizard.chrome import (
    render_nav_footer,
    render_summary_table,
    render_wizard_header,
)
from mediaforge.cli.wizard.steps._base import BaseStep
from mediaforge.utils.console import console


class ConfirmationStep(BaseStep):
    def __init__(
        self,
        title: str = "Confirm",
        key: str = "__confirm__",
        summary_keys: list[tuple[str, str]] | None = None,
    ) -> None:
        super().__init__(key, title, skip_when=None)
        self._summary_keys: list[tuple[str, str]] = summary_keys or []

    def run(self, ctx: StepContext) -> StepSignal:
        render_wizard_header(ctx)

        rows = self._build_rows(ctx.state)
        if rows:
            console.print(render_summary_table(rows))
        else:
            console.print("  [dim]No options were configured.[/]\n")

        render_nav_footer(is_first=ctx.is_first, confirm=True)
        return self._prompt()

    # ── internal ──────────────────────────────────────────────────────────────

    def _build_rows(self, state: WizardState) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for sk, label in self._summary_keys:
            raw = state.get(sk)
            if raw is None:
                continue
            display = state.get(f"__display_{sk}")
            if display is not None:
                rows.append((label, str(display)))
            elif isinstance(raw, bool):
                rows.append((label, "Yes" if raw else "No"))
            elif isinstance(raw, list):
                rows.append((label, ", ".join(str(v) for v in raw)))
            else:
                rows.append((label, str(raw)))
        return rows

    def _prompt(self) -> StepSignal:
        while True:
            raw = (
                console.input(
                    "  [bold cyan]›[/] [dim](Enter to confirm, p to go back, c to cancel)[/] "
                )
                .strip()
                .lower()
            )

            if raw in {"", "y", "yes"}:
                return StepSignal.NEXT
            if raw in {"p", "back", "prev"}:
                return StepSignal.BACK
            if raw in {"c", "cancel", "q"}:
                return StepSignal.CANCEL

            console.print("  [error]Enter, p, or c.[/]")
