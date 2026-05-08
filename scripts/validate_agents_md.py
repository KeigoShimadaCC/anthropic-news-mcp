#!/usr/bin/env python3
"""Validate AGENTS.md: check file references exist and CI commands are documented."""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
AGENTS_MD = REPO_ROOT / "AGENTS.md"


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
    gate_section = re.search(
        r"## CI Quality Gates\n(.*?)(?=\n##|\Z)", content, re.DOTALL
    )
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


def main() -> int:
    if not AGENTS_MD.exists():
        print("ERROR: AGENTS.md not found at repo root", file=sys.stderr)
        return 1

    content = AGENTS_MD.read_text()
    all_errors: list[str] = []

    all_errors.extend(check_required_sections(content))
    all_errors.extend(check_file_references(content))
    all_errors.extend(check_ci_gate_coverage(content))

    if all_errors:
        print("AGENTS.md validation failed:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"AGENTS.md validation passed ({len(content)} bytes, no broken links or missing sections)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
