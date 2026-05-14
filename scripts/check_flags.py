#!/usr/bin/env python3
"""Detect stale or misconfigured feature flags.

Three checks are performed against ``src/anthropic_news_mcp/flags.py``:

1. **Stale flag** — defined on ``FeatureFlags`` but never referenced as
   ``FLAGS.<name>`` anywhere in the source tree.
2. **Undefined reference** — ``FLAGS.<name>`` used in source but ``<name>``
   is not a field on the dataclass.
3. **Env-var drift** — every ``_bool_env("KEY", ...)`` call in ``from_env``
   must correspond to documentation in ``.env.example`` so agents and ops
   know how to override the flag. (This is the lifecycle process check.)

The script is part of the CI quality gate. Add new flags to ``FLAGS`` and
``.env.example`` together; remove them from both when they're permanent.
"""

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FLAGS_MODULE = REPO_ROOT / "src" / "anthropic_news_mcp" / "flags.py"
SRC_DIR = REPO_ROOT / "src" / "anthropic_news_mcp"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


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


def get_env_keys_in_flags_module() -> list[str]:
    """Extract the env-var key from every ``_bool_env(KEY, ...)`` call."""
    pattern = re.compile(r'_bool_env\(\s*"([^"]+)"')
    return pattern.findall(FLAGS_MODULE.read_text())


def get_documented_env_keys() -> set[str]:
    if not ENV_EXAMPLE.exists():
        return set()
    keys: set[str] = set()
    for line in ENV_EXAMPLE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" in stripped:
            keys.add(stripped.split("=", 1)[0].strip())
    return keys


def main() -> int:
    defined = get_defined_flags()
    used = get_used_flags()
    env_keys = get_env_keys_in_flags_module()
    documented = get_documented_env_keys()

    stale = [f for f in defined if f not in used]
    undefined_refs = sorted(f for f in used if f not in defined)
    undocumented_envs = [k for k in env_keys if k not in documented]

    errors: list[str] = []
    if stale:
        errors.append(f"Stale flags (defined but never used in source): {stale}")
    if undefined_refs:
        errors.append(
            f"Undefined flag references (FLAGS.X where X not in FeatureFlags): {undefined_refs}"
        )
    if undocumented_envs:
        errors.append(
            "Env-var drift — these keys are read by flags.py but not documented "
            f"in .env.example: {undocumented_envs}"
        )

    if errors:
        print("Feature flag check FAILED:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(
        f"Feature flag check passed: {len(defined)} flags, "
        f"{len(env_keys)} env vars, all referenced and documented."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
