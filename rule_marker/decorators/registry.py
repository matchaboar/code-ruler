"""Global decorator registry: decorator_name → (decorator_fn, rule_id)."""

from __future__ import annotations

from typing import Any, Callable

# Global registry: decorator_name -> (decorator_function, rule_id or None)
_REGISTRY: dict[str, tuple[Callable[..., Any], int | None]] = {}


def register_decorator(
    name: str, decorator_fn: Callable[..., Any], rule_id: int | None = None
) -> None:
    """Register a decorator in the global registry."""
    _REGISTRY[name] = (decorator_fn, rule_id)


def get_decorator(name: str) -> tuple[Callable[..., Any], int | None] | None:
    """Look up a decorator by name."""
    return _REGISTRY.get(name)


def list_decorators() -> dict[str, tuple[Callable[..., Any], int | None]]:
    """Return a copy of the decorator registry."""
    return dict(_REGISTRY)


def is_registered(name: str) -> bool:
    """Check if a decorator name is registered."""
    return name in _REGISTRY
