"""Generate and test enforcer scripts for rules."""

from __future__ import annotations

import ast
import re
from typing import Any

from anthropic import AnthropicBedrock
from sqlalchemy.orm import Session

from code_ruler.db.models import EnforcerScript, Rule
from code_ruler.db.repository import create_enforcer_script, get_enforcer_by_rule_id
from code_ruler.llm.client import TraceCollector, call_llm, set_trace_collector
from code_ruler.llm.prompts import ENFORCER_FIX_USER, ENFORCER_SYSTEM, ENFORCER_USER

MAX_ATTEMPTS = 3

# Restricted builtins for sandboxed exec (mirrors function_type_checks.py)
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

_ALLOWED_IMPORTS = {"ast", "re", "string", "textwrap", "collections"}


def _safe_import(name: str, *args: object, **kwargs: object) -> object:
    """Restricted __import__ that only allows safe stdlib modules."""
    if name not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import of '{name}' is not allowed in enforcer scripts")
    return __builtins__["__import__"](name, *args, **kwargs) if isinstance(__builtins__, dict) else __import__(name, *args, **kwargs)


_SAFE_BUILTINS["__import__"] = _safe_import


def generate_enforcer(
    client: AnthropicBedrock,
    session: Session,
    rule: Rule,
    model: str,
) -> EnforcerScript:
    """Generate an enforcer script for a rule.

    For function_type rules with existing linter_source, copies it directly.
    Otherwise uses LLM generation with retry logic.
    """
    # For function_type rules with existing linter_source, copy directly
    if rule.category == "function_type" and rule.function_type_rule:
        ftr = rule.function_type_rule
        return create_enforcer_script(
            session,
            rule_id=rule.id,
            enforcer_source=ftr.linter_source,
            check_type="function",
            decorator_source=ftr.decorator_source,
            test_code=rule.negative_example,
            test_result="passed",
            test_output="Copied from existing function_type linter_source",
            attempt_count=0,
            status="passed",
        )

    # LLM-based generation with retry
    check_type = "module"
    return _generate_with_retry(client, session, rule, model, check_type)


def _generate_with_retry(
    client: AnthropicBedrock,
    session: Session,
    rule: Rule,
    model: str,
    check_type: str,
) -> EnforcerScript:
    """Generate enforcer with up to MAX_ATTEMPTS retries."""
    collector = TraceCollector()
    set_trace_collector(collector)

    previous_source: str | None = None
    previous_error: str | None = None
    last_source = ""
    last_output = ""

    # Mark as generating
    enforcer = create_enforcer_script(
        session,
        rule_id=rule.id,
        enforcer_source="",
        check_type=check_type,
        test_code=rule.negative_example,
        status="generating",
    )
    session.commit()

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            # Build prompt
            if attempt == 1 or previous_source is None:
                user_msg = ENFORCER_USER.format(
                    title=rule.title,
                    description=rule.description,
                    category=rule.category,
                    positive_example=rule.positive_example or "# (none provided)",
                    negative_example=rule.negative_example or "# (none provided)",
                )
            else:
                user_msg = ENFORCER_FIX_USER.format(
                    title=rule.title,
                    description=rule.description,
                    category=rule.category,
                    previous_source=previous_source,
                    error=previous_error,
                    negative_example=rule.negative_example or "# (none provided)",
                )

            # Call LLM
            print(f"  [Enforcer] Attempt {attempt}/{MAX_ATTEMPTS} for {rule.slug}...")
            raw = call_llm(client, ENFORCER_SYSTEM, user_msg, model)
            source = _extract_code(raw)

            if not source:
                previous_source = raw
                previous_error = "Could not extract Python code from LLM response"
                last_source = raw
                last_output = previous_error
                continue

            # Test the enforcer
            success, output = _test_enforcer(source, check_type, rule)
            last_source = source
            last_output = output

            if success:
                enforcer.enforcer_source = source
                enforcer.test_result = "passed"
                enforcer.test_output = output
                enforcer.attempt_count = attempt
                enforcer.status = "passed"
                enforcer.dd_traces = collector.to_dicts()
                session.flush()
                session.commit()
                set_trace_collector(None)
                print(f"  [Enforcer] Passed on attempt {attempt}")
                return enforcer

            # Failed — prepare for retry
            previous_source = source
            previous_error = output
            print(f"  [Enforcer] Attempt {attempt} failed: {output[:120]}")

        # All attempts exhausted
        enforcer.enforcer_source = last_source
        enforcer.test_result = "failed"
        enforcer.test_output = last_output
        enforcer.attempt_count = MAX_ATTEMPTS
        enforcer.status = "failed"
        enforcer.dd_traces = collector.to_dicts()
        session.flush()
        session.commit()
        set_trace_collector(None)
        print(f"  [Enforcer] Failed after {MAX_ATTEMPTS} attempts for {rule.slug}")
        return enforcer

    except Exception as e:
        enforcer.status = "failed"
        enforcer.test_result = "failed"
        enforcer.test_output = f"Generation error: {e}"
        enforcer.dd_traces = collector.to_dicts()
        session.flush()
        session.commit()
        set_trace_collector(None)
        raise


def _extract_code(raw: str) -> str | None:
    """Extract Python code from markdown fenced code blocks."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", raw, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: if it looks like it starts with def check, use it directly
    stripped = raw.strip()
    if stripped.startswith("def check") or stripped.startswith("import ast"):
        return stripped
    return None


def _test_enforcer(
    source: str,
    check_type: str,
    rule: Rule,
) -> tuple[bool, str]:
    """Test an enforcer script against the rule's negative example.

    Returns (success, output) where success means the check found violations
    in the negative example.
    """
    negative_example = rule.negative_example
    if not negative_example:
        return False, "Rule has no negative_example to test against"

    # Parse the negative example
    try:
        tree = ast.parse(negative_example)
    except SyntaxError as e:
        return False, f"Failed to parse negative_example: {e}"

    # Compile and exec the enforcer source in sandbox
    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "ast": ast,
    }

    try:
        exec(compile(source, "<enforcer>", "exec"), namespace)
    except Exception as e:
        return False, f"Enforcer source compilation error: {e}"

    check_fn = namespace.get("check")
    if check_fn is None:
        return False, "Enforcer source does not define a check() function"

    # Run the check
    try:
        if check_type == "function":
            # Find the first function def in the negative example
            func_nodes = [
                n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not func_nodes:
                return False, "No function definition found in negative_example for function-type check"
            result = check_fn(func_nodes[0], negative_example)
        else:
            result = check_fn(tree, negative_example)
    except Exception as e:
        return False, f"Enforcer check() raised an error: {e}"

    if not isinstance(result, list):
        return False, f"check() returned {type(result).__name__}, expected list"

    if len(result) == 0:
        return False, "check() returned no violations for the negative example (expected at least one)"

    violations_str = "\n".join(f"  - {msg}" for msg in result)

    # Optionally verify positive example doesn't trigger
    if rule.positive_example:
        try:
            pos_tree = ast.parse(rule.positive_example)
            if check_type == "function":
                func_nodes = [
                    n for n in ast.walk(pos_tree)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if func_nodes:
                    pos_result = check_fn(func_nodes[0], rule.positive_example)
                else:
                    pos_result = []
            else:
                pos_result = check_fn(pos_tree, rule.positive_example)
            if pos_result:
                pos_violations = "\n".join(f"  - {msg}" for msg in pos_result)
                return False, (
                    f"check() incorrectly flagged the positive example:\n{pos_violations}"
                )
        except Exception:
            pass  # Don't fail on positive example issues

    return True, f"Found {len(result)} violation(s) in negative example:\n{violations_str}"
