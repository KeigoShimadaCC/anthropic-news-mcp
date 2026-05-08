#!/usr/bin/env python3
"""Deterministic offline eval runner for MCP tool behavior."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from seed import seed_eval_cache

_ROOT = Path(__file__).parent.parent
_EVALS_DIR = Path(__file__).parent
_CASES = _EVALS_DIR / "offline_cases.yaml"
_RESULTS_DIR = _EVALS_DIR / "results"
_RESULTS_DIR.mkdir(exist_ok=True)


def load_cases(ids: list[str] | None = None) -> list[dict[str, Any]]:
    raw = _CASES.read_text(encoding="utf-8")
    try:
        cases = json.loads(raw)
    except json.JSONDecodeError:
        import yaml

        cases = yaml.safe_load(raw)
    if not isinstance(cases, list):
        raise ValueError("offline_cases.yaml must contain a list of cases")
    if ids:
        requested = set(ids)
        cases = [case for case in cases if case.get("id") in requested]
    return cases


async def _call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(_ROOT / "src"))
    from anthropic_news_mcp.server import mcp

    result = await mcp.call_tool(name, args)
    if isinstance(result, tuple):
        content_list, _ = result
        text = content_list[0].text if content_list else "{}"
    elif isinstance(result, list):
        text = result[0].text if result else "{}"
    elif hasattr(result, "content"):
        text = result.content[0].text
    else:
        text = str(result)
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{name} returned non-object JSON")
    return parsed


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _check_case(case: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    serialized = json.dumps(payload, sort_keys=True)

    error_contains = case.get("error_contains")
    if error_contains is not None:
        error = payload.get("error")
        if isinstance(error, str):
            error_text = error
        elif isinstance(error, dict) and isinstance(error.get("message"), str):
            error_text = error["message"]
        else:
            return ["expected error response"]
        for fragment in error_contains:
            if str(fragment) not in error_text:
                failures.append(f"error missing {fragment!r}")
        return failures

    if "error" in payload:
        failures.append(f"unexpected error: {payload['error']}")

    min_items = case.get("min_items")
    if min_items is not None and len(_items(payload)) < int(min_items):
        failures.append(f"expected at least {min_items} items, got {len(_items(payload))}")

    expected_source_keys = set(case.get("item_source_keys", []))
    if expected_source_keys:
        returned = {item.get("source_key") for item in _items(payload)}
        missing = expected_source_keys - returned
        if missing:
            failures.append(f"missing source keys: {sorted(missing)}")

    for fragment in case.get("response_contains", []):
        if str(fragment) not in serialized:
            failures.append(f"response missing {fragment!r}")

    return failures


async def run(ids: list[str] | None = None) -> int:
    cases = load_cases(ids)
    if not cases:
        print("No offline eval cases selected")
        return 1

    with tempfile.TemporaryDirectory(prefix="anthropic-news-offline-eval-") as tmp:
        seed_eval_cache(Path(tmp) / "offline_eval.db")

        results = []
        failed = 0
        print(f"Running {len(cases)} offline eval cases...")
        for case in cases:
            payload = await _call_tool(case["tool"], case.get("args", {}))
            failures = _check_case(case, payload)
            failed += bool(failures)
            status = "FAIL" if failures else "PASS"
            print(f"  [{case['id']}] {case['tool']} -> {status}")
            results.append(
                {
                    "id": case["id"],
                    "tool": case["tool"],
                    "args": case.get("args", {}),
                    "failures": failures,
                    "payload": payload,
                }
            )

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output = {
        "timestamp": timestamp,
        "n_cases": len(cases),
        "passed": failed == 0,
        "failed": failed,
        "results": results,
    }
    out_path = _RESULTS_DIR / f"offline_eval_{timestamp}.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Results written to {out_path.relative_to(_ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run deterministic offline eval cases")
    parser.add_argument("--ids", help="Comma-separated case IDs to run")
    args = parser.parse_args()
    selected = args.ids.split(",") if args.ids else None
    raise SystemExit(asyncio.run(run(selected)))
