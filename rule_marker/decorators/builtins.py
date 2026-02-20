"""Hand-written common decorators."""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from rule_marker.decorators.registry import register_decorator

F = TypeVar("F", bound=Callable[..., Any])


def _make_marker(marker_type: str) -> Callable[[F], F]:
    """Create a marker decorator that stamps __rule_marker_type__ on the function."""

    def decorator(func: F) -> F:
        func.__rule_marker_type__ = marker_type  # type: ignore[attr-defined]
        functools.update_wrapper(decorator, func)
        return func

    return decorator


def pure_function(func: F) -> F:
    """Mark a function as pure (no side effects, deterministic output)."""
    func.__rule_marker_type__ = "pure_function"  # type: ignore[attr-defined]
    return func


def api_handler(func: F) -> F:
    """Mark a function as an API handler."""
    func.__rule_marker_type__ = "api_handler"  # type: ignore[attr-defined]
    return func


# Register built-in decorators
register_decorator("pure_function", pure_function)
register_decorator("api_handler", api_handler)
