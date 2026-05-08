#!/usr/bin/env python3
"""Detect stale feature flags — defined in flags.py but unused in source, or used but undefined."""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FLAGS_MODULE = REPO_ROOT / "src" / "anthropic_news_mcp" / "flags.py"
SRC_DIR = REPO_ROOT / "src" / "anthropic_news_mcp"


def get_defined_flags() -> list[str]:
    tree = ast.parse(FLAGS_MODULE.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "FeatureFlags":
            return [
                f.target.id  # type: ignore[union-attr]
                for f in node.body
                if isinstance(f, ast.AnnAssign) and isinstance(f.target, ast.Name)
            ]
    return []


def get_used_flags() -> set[str]:
    used: set[str] = set()
    pattern = re.compile(r"\bFLAGS\.(\w+)")
    for py_file in SRC_DIR.rglob("*.py"):
        if py_file.name == "flags.py":
            continue
        used.update(pattern.findall(py_file.read_text()))
    return used


def main() -> int:
    defined = get_defined_flags()
    used = get_used_flags()

    stale = [f for f in defined if f not in used]
    undefined_refs = sorted(f for f in used if f not in defined)

    errors: list[str] = []
    if stale:
        errors.append(f"Stale flags (defined but never used in source): {stale}")
    if undefined_refs:
        errors.append(
            f"Undefined flag references (FLAGS.X where X not in FeatureFlags): {undefined_refs}"
        )

    if errors:
        print("Feature flag check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(f"Feature flag check passed: {len(defined)} flags defined, all referenced in source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
