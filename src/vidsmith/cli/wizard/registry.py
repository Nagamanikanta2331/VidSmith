"""
Extension registries — the only two places where future AI features or
third-party plugins register new capabilities without modifying existing code.

Usage (from a plugin / AI module):

    from vidsmith.cli.wizard.registry import WizardRegistry, StepRegistry

    # Add a brand-new wizard action
    WizardRegistry.register("ai_captions", build_ai_captions_wizard)

    # Add a brand-new step type that the wizard DSL can reference by name
    StepRegistry.register("ai_enhance", AIEnhanceStep)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vidsmith.cli.wizard.base import Wizard

# Type aliases
WizardFactory = Callable[[], Wizard]
StepFactory = Callable[..., Any]  # returns a WizardStep-compatible object


class _WizardRegistry:
    def __init__(self) -> None:
        self._store: dict[str, WizardFactory] = {}

    def register(self, name: str, factory: WizardFactory) -> None:
        self._store[name] = factory

    def get(self, name: str) -> WizardFactory | None:
        return self._store.get(name)

    def names(self) -> list[str]:
        return sorted(self._store)

    def __contains__(self, name: str) -> bool:
        return name in self._store


class _StepRegistry:
    def __init__(self) -> None:
        self._store: dict[str, StepFactory] = {}

    def register(self, type_name: str, factory: StepFactory) -> None:
        self._store[type_name] = factory

    def build(self, type_name: str, **config: Any) -> Any:
        factory = self._store.get(type_name)
        if factory is None:
            raise KeyError(f"No step registered for type {type_name!r}")
        return factory(**config)

    def get(self, type_name: str) -> StepFactory | None:
        return self._store.get(type_name)

    def names(self) -> list[str]:
        return sorted(self._store)

    def __contains__(self, type_name: str) -> bool:
        return type_name in self._store


# Public singletons — import and use directly
WizardRegistry = _WizardRegistry()
StepRegistry = _StepRegistry()
