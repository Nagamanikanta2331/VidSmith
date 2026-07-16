"""
Public API for the wizard framework.

Typical usage:

    from mediaforge.cli.wizard import Wizard, WizardState, WizardRegistry

    # Run a built-in wizard:
    from mediaforge.cli.wizard.dispatcher import dispatch_wizard
    dispatch_wizard("video", result)

    # Register a plugin wizard (no existing code modified):
    WizardRegistry.register("my_feature", build_my_wizard)
"""

from mediaforge.cli.wizard.base import (
    StepContext,
    StepSignal,
    Wizard,
    WizardState,
    WizardStep,
)
from mediaforge.cli.wizard.registry import StepRegistry, WizardRegistry

__all__ = [
    "StepContext",
    "StepRegistry",
    "StepSignal",
    "Wizard",
    "WizardRegistry",
    "WizardState",
    "WizardStep",
]
