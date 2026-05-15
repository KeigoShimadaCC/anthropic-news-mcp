#!/usr/bin/env python3
"""Validate AGENTS.md: check file references exist, CI commands are documented,
and the documented Quick Start commands are still executable.

The "smoke" mode runs read-only versions of the documented commands (e.g.
``ruff check --no-fix``, ``pytest --collect-only``) to confirm they remain
runnable. Run it locally with ``--smoke`` or in CI as a separate step.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"

# Smoke-test commands. Each entry is (label, argv). They must all be read-only
# and fast (< 30s typical). The test passes if every command exits 0.
SMOKE_COMMANDS: list[tuple[str, list[str]]] = [
    ("ruff check", ["ruff", "check", ".", "--no-fix"]),
    ("ruff format check", ["ruff", "format", "--check", "."]),
    ("pytest collect", ["pytest", "--collect-only", "-q"]),
]


def check_file_references(content: str) -> list[str]:
    """Find markdown links to local files and verify they exist."""
    errors: list[str] = []
    # Match [text](path) where path doesn't start with http
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        path_str = match.group(2)
        if path_str.startswith("http") or path_str.startswith("#"):
            continue
        # Strip leading ./ and ../ characters individually
        path_str = path_str.lstrip(".").lstrip("/")
        candidates = [
            REPO_ROOT / path_str,
            REPO_ROOT / match.group(2).lstrip("/"),
        ]
        if not any(c.exists() for c in candidates):
            errors.append(f"Broken link: [{match.group(1)}]({match.group(2)})")
    return errors


def check_required_sections(content: str) -> list[str]:
    """Ensure required sections are present in AGENTS.md."""
    required = [
        "## Quick Start",
        "## Architecture",
        "## Key Rules",
        "## CI Quality Gates",
        "## Environment Variables",
    ]
    errors: list[str] = []
    for section in required:
        if section not in content:
            errors.append(f"Missing required section: {section}")
    return errors


def check_ci_gate_coverage(content: str) -> list[str]:
    """Verify each CI gate listed in AGENTS.md maps to a step in ci.yml."""
    ci_yml = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    if not ci_yml.exists():
        return ["ci.yml not found — cannot validate CI gate coverage"]

    ci_content = ci_yml.read_text()
    errors: list[str] = []

    # Extract commands from the CI Quality Gates section of AGENTS.md
    gate_section = re.search(r"## CI Quality Gates\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
    if not gate_section:
        return ["CI Quality Gates section not found in AGENTS.md"]

    # Find backtick-wrapped commands
    commands = re.findall(r"`([^`]+)`", gate_section.group(1))
    tool_map = {
        "ruff": "ruff",
        "mypy": "mypy",
        "pytest": "pytest",
        "vulture": "vulture",
        "radon": "radon",
        "deptry": "deptry",
        "pylint": "pylint",
    }
    for cmd in commands:
        first_word = cmd.split()[0]
        tool = tool_map.get(first_word)
        if tool and tool not in ci_content:
            errors.append(f"CI gate '{first_word}' documented in AGENTS.md but not found in ci.yml")

    return errors


def _resolve(executable: str) -> str | None:
    """Prefer ``.venv/bin/<executable>`` if present, fall back to PATH."""
    venv_bin = REPO_ROOT / ".venv" / "bin" / executable
    if venv_bin.is_file():
        return str(venv_bin)
    return shutil.which(executable)


def run_smoke_commands() -> list[str]:
    """Execute documented commands in dry-run/collect-only mode and return errors."""
    errors: list[str] = []
    for label, argv in SMOKE_COMMANDS:
        resolved = _resolve(argv[0])
        if resolved is None:
            errors.append(f"smoke[{label}]: '{argv[0]}' not on PATH and not in .venv/bin")
            continue
        full_argv = [resolved, *argv[1:]]
        try:
            result = subprocess.run(  # noqa: S603 — argv is a hard-coded literal list
                full_argv,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"smoke[{label}]: timed out after 120s")
            continue
        if result.returncode != 0:
            tail = (result.stdout + result.stderr).strip().splitlines()[-5:]
            errors.append(f"smoke[{label}]: exit {result.returncode}\n    " + "\n    ".join(tail))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Also execute documented commands in read-only mode.",
    )
    args = parser.parse_args()

    if not AGENTS_MD.exists():
        print("ERROR: AGENTS.md not found at repo root", file=sys.stderr)
        return 1

    content = AGENTS_MD.read_text()
    all_errors: list[str] = []

    all_errors.extend(check_required_sections(content))
    all_errors.extend(check_file_references(content))
    all_errors.extend(check_ci_gate_coverage(content))

    if args.smoke:
        all_errors.extend(run_smoke_commands())

    if all_errors:
        print("AGENTS.md validation failed:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    mode = " (with smoke tests)" if args.smoke else ""
    print(
        f"AGENTS.md validation passed{mode} "
        f"({len(content)} bytes, no broken links or missing sections)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
