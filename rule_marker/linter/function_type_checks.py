"""Loads and executes linter_source from FunctionTypeRule."""

from __future__ import annotations

import ast
from typing import Any

from rule_marker.decorators.registry import is_registered
from rule_marker.linter.violations import Violation

# Restricted builtins for sandboxed exec
_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "hasattr": hasattr,
    "getattr": getattr,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


def run_function_type_checks(
    tree: ast.Module,
    source: str,
    file: str,
    function_type_rules: list,
) -> list[Violation]:
    """Run function type checks on decorated functions."""
    violations: list[Violation] = []

    # Build a map of decorator_name -> (linter_source, rule)
    linter_map: dict[str, tuple[str, Any]] = {}
    for ftr in function_type_rules:
        linter_map[ftr.decorator_name] = (ftr.linter_source, ftr.rule)

    # Walk the AST for function definitions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Check each decorator
        for decorator in node.decorator_list:
            dec_name = _get_decorator_name(decorator)
            if dec_name and dec_name in linter_map:
                linter_source, rule = linter_map[dec_name]
                messages = _run_linter(linter_source, node, source, dec_name)
                for msg in messages:
                    violations.append(
                        Violation(
                            file=file,
                            line=node.lineno,
                            column=node.col_offset,
                            rule_slug=rule.slug,
                            severity=rule.severity,
                            message=msg,
                        )
                    )

            # Also check built-in registered decorators
            if dec_name and is_registered(dec_name) and dec_name not in linter_map:
                messages = _run_builtin_check(dec_name, node, source)
                for msg in messages:
                    violations.append(
                        Violation(
                            file=file,
                            line=node.lineno,
                            column=node.col_offset,
                            rule_slug=dec_name,
                            severity="warning",
                            message=msg,
                        )
                    )

    return violations


def _get_decorator_name(decorator: ast.expr) -> str | None:
    """Extract the decorator name from an AST node."""
    if isinstance(decorator, ast.Name):
        return decorator.id
    if isinstance(decorator, ast.Attribute):
        return decorator.attr
    if isinstance(decorator, ast.Call):
        return _get_decorator_name(decorator.func)
    return None


def _run_linter(
    linter_source: str,
    func_node: ast.FunctionDef,
    source: str,
    decorator_name: str,
) -> list[str]:
    """Execute LLM-generated linter code in a sandboxed namespace."""
    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "ast": ast,
    }

    try:
        exec(compile(linter_source, f"<linter:{decorator_name}>", "exec"), namespace)
        check_fn = namespace.get("check")
        if check_fn is None:
            return [f"Linter for '{decorator_name}' does not define a check() function"]
        result = check_fn(func_node, source)
        if isinstance(result, list):
            return [str(msg) for msg in result]
    except Exception as e:
        return [f"Linter error for '{decorator_name}': {e}"]

    return []


def _run_builtin_check(
    decorator_name: str,
    func_node: ast.FunctionDef,
    source: str,
) -> list[str]:
    """Run built-in checks for known decorator types."""
    if decorator_name == "pure_function":
        return _check_pure_function(func_node, source)
    if decorator_name == "api_handler":
        return _check_api_handler(func_node, source)
    return []


def _check_pure_function(func_node: ast.FunctionDef, source: str) -> list[str]:
    """Check that a pure_function doesn't have side effects."""
    violations = []
    impure_calls = {"print", "open", "write", "input", "exit", "quit"}

    for node in ast.walk(func_node):
        # Check for impure function calls
        if isinstance(node, ast.Call):
            name = _get_call_name(node)
            if name in impure_calls:
                violations.append(f"pure_function must not call '{name}'")

        # Check for global/nonlocal statements
        if isinstance(node, ast.Global):
            violations.append("pure_function must not use 'global' statement")
        if isinstance(node, ast.Nonlocal):
            violations.append("pure_function must not use 'nonlocal' statement")

    return violations


def _check_api_handler(func_node: ast.FunctionDef, source: str) -> list[str]:
    """Check that an api_handler has proper structure."""
    violations = []

    # Check for return type annotation
    if func_node.returns is None:
        violations.append("api_handler should have a return type annotation")

    return violations


def _get_call_name(node: ast.Call) -> str | None:
    """Extract the function name from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None
