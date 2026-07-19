"""AST guard for first-N patterns in production audit entry points."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path


BANNED_IDENTIFIERS = {
    "DEFAULT_N_CASES",
    "MAX_CASES",
    "N_CASES",
    "first_n",
    "head",
    "max_cases",
}


def _case_collection(expression: ast.expr) -> bool:
    if isinstance(expression, ast.Name):
        name = expression.id.lower()
    elif isinstance(expression, ast.Attribute):
        name = expression.attr.lower()
    else:
        return False
    return any(token in name for token in ("case", "cohort", "patient"))


def scan_source(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BANNED_IDENTIFIERS:
            violations.append(f"{path}:{node.lineno}: banned identifier {node.id}")
        if isinstance(node, ast.Attribute) and node.attr in BANNED_IDENTIFIERS:
            violations.append(f"{path}:{node.lineno}: banned attribute {node.attr}")
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
            if (
                _case_collection(node.value)
                and node.slice.lower is None
                and node.slice.upper is not None
            ):
                violations.append(f"{path}:{node.lineno}: prefix slice is forbidden")
    return violations


def scan_production_sources(paths: Iterable[Path]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        violations.extend(scan_source(path))
    return violations
