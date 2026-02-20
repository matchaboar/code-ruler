"""AST visitors for lint/best-practice rules."""

from __future__ import annotations

import ast

from rule_marker.linter.violations import Violation


class BareExceptChecker(ast.NodeVisitor):
    """Check for bare except clauses."""

    def __init__(self, file: str) -> None:
        self.file = file
        self.violations: list[Violation] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.violations.append(
                Violation(
                    file=self.file,
                    line=node.lineno,
                    column=node.col_offset,
                    rule_slug="no-bare-except",
                    severity="warning",
                    message="Do not use bare except clauses",
                    suggestion="Catch a specific exception type (e.g., `except ValueError:`)",
                )
            )
        self.generic_visit(node)


class MutableDefaultArgChecker(ast.NodeVisitor):
    """Check for mutable default arguments."""

    MUTABLE_TYPES = {"List", "Dict", "Set", "list", "dict", "set"}

    def __init__(self, file: str) -> None:
        self.file = file
        self.violations: list[Violation] = []

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.violations.append(
                    Violation(
                        file=self.file,
                        line=default.lineno,
                        column=default.col_offset,
                        rule_slug="no-mutable-default",
                        severity="error",
                        message="Do not use mutable default arguments",
                        suggestion="Use None as default and create the mutable inside the function",
                    )
                )
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef


def run_ast_checks(tree: ast.Module, source: str, file: str) -> list[Violation]:
    """Run all built-in AST checks on a parsed module."""
    violations: list[Violation] = []

    checkers = [
        BareExceptChecker(file),
        MutableDefaultArgChecker(file),
    ]

    for checker in checkers:
        checker.visit(tree)
        violations.extend(checker.violations)

    return violations
