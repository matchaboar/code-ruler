"""Main scan loop: find .py files, parse AST, apply checks."""

from __future__ import annotations

import ast
from pathlib import Path

from rule_marker.linter.violations import Violation


class LintEngine:
    """AST-based lint engine."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path
        self._function_type_rules: list = []
        self._active_rules: list = []

        if db_path:
            self._load_rules()

    def _load_rules(self) -> None:
        """Load rules and dynamic decorators from the database."""
        from rule_marker.db.reader import get_active_rules, get_function_type_rules, get_read_session
        from rule_marker.decorators.dynamic import load_dynamic_decorators

        session = get_read_session(self.db_path)
        self._active_rules = get_active_rules(session)
        self._function_type_rules = get_function_type_rules(session)
        load_dynamic_decorators(self._function_type_rules)
        session.close()

    def scan(self, paths: list[str]) -> list[Violation]:
        """Scan files for violations."""
        from rule_marker.linter.ast_checks import run_ast_checks
        from rule_marker.linter.function_type_checks import run_function_type_checks

        violations: list[Violation] = []

        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                violations.extend(self._scan_file(path, run_ast_checks, run_function_type_checks))
            elif path.is_dir():
                for py_file in path.rglob("*.py"):
                    violations.extend(self._scan_file(py_file, run_ast_checks, run_function_type_checks))

        return violations

    def _scan_file(self, path: Path, run_ast_checks, run_function_type_checks) -> list[Violation]:
        """Scan a single Python file."""
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            return []

        violations: list[Violation] = []
        file_str = str(path)

        # Run AST-based checks for lint/best_practice rules
        violations.extend(run_ast_checks(tree, source, file_str))

        # Run function type checks
        violations.extend(
            run_function_type_checks(tree, source, file_str, self._function_type_rules)
        )

        return violations
