"""Loads LLM-generated decorator source from DB, compiles, and registers."""

from __future__ import annotations

from typing import Any, Callable

from code_ruler.db.models import FunctionTypeRule
from rule_marker.decorators.registry import register_decorator


def load_dynamic_decorators(function_type_rules: list[FunctionTypeRule]) -> int:
    """Load and register decorators from function type rules.

    Returns the number of successfully loaded decorators.
    """
    loaded = 0
    for ftr in function_type_rules:
        try:
            decorator_fn = _compile_decorator(ftr.decorator_name, ftr.decorator_source)
            register_decorator(ftr.decorator_name, decorator_fn, rule_id=ftr.rule_id)
            loaded += 1
        except Exception as e:
            print(f"Warning: Failed to load decorator '{ftr.decorator_name}': {e}")

    return loaded


def _compile_decorator(name: str, source: str) -> Callable[..., Any]:
    """Compile decorator source code and extract the decorator function."""
    namespace: dict[str, Any] = {}
    exec(compile(source, f"<decorator:{name}>", "exec"), namespace)

    if name not in namespace:
        raise ValueError(f"Decorator source does not define '{name}'")

    return namespace[name]
