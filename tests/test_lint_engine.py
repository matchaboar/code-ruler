"""Tests for the lint engine and AST checks."""

from __future__ import annotations

import tempfile
from pathlib import Path

from rule_marker.linter.engine import LintEngine
from rule_marker.linter.violations import Violation


def test_bare_except_detected():
    """Test that bare except clauses are detected."""
    code = """\
try:
    do_something()
except:
    pass
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    assert len(violations) == 1
    assert violations[0].rule_slug == "no-bare-except"


def test_specific_except_ok():
    """Test that specific except clauses pass."""
    code = """\
try:
    do_something()
except ValueError:
    pass
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    bare_except = [v for v in violations if v.rule_slug == "no-bare-except"]
    assert len(bare_except) == 0


def test_mutable_default_detected():
    """Test that mutable default arguments are detected."""
    code = """\
def foo(items=[]):
    items.append(1)
    return items
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    mutable = [v for v in violations if v.rule_slug == "no-mutable-default"]
    assert len(mutable) == 1


def test_pure_function_with_print():
    """Test that pure_function decorator with print is flagged."""
    code = """\
from rule_marker.decorators import pure_function

@pure_function
def calculate(x):
    print(x)
    return x * 2
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    pure_violations = [v for v in violations if v.rule_slug == "pure_function"]
    assert len(pure_violations) == 1
    assert "print" in pure_violations[0].message


def test_pure_function_clean():
    """Test that a clean pure_function passes."""
    code = """\
from rule_marker.decorators import pure_function

@pure_function
def calculate(x):
    return x * 2
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    pure_violations = [v for v in violations if v.rule_slug == "pure_function"]
    assert len(pure_violations) == 0


def test_scan_directory():
    """Test scanning a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "good.py").write_text("x = 1\n")
        Path(tmpdir, "bad.py").write_text("try:\n    pass\nexcept:\n    pass\n")

        engine = LintEngine()
        violations = engine.scan([tmpdir])

    assert any(v.rule_slug == "no-bare-except" for v in violations)


def test_no_violations_clean_file():
    """Test that clean code has no violations."""
    code = """\
def add(a: int, b: int) -> int:
    return a + b
"""
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        f.flush()
        engine = LintEngine()
        violations = engine.scan([f.name])

    assert len(violations) == 0
