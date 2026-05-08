"""Live source-health audit CLI."""

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import TypedDict, cast

from .config import SOURCE_REGISTRY, SourceConfig
from .models import NewsItem
from .retrieval import _sanitize_error

_CANONICAL_REQUIRED = {
    "anthropic-newsroom",
    "anthropic-status",
    "anthropic-research",
    "anthropic-engineering",
    "anthropic-docs-api",
    "anthropic-docs-claude-apps",
    "anthropic-docs-system-prompts",
    "anthropic-support-release-notes",
    "anthropic-economic-index",
}
_REGULARLY_UPDATED = {
    "anthropic-newsroom": 180,
    "anthropic-research": 365,
    "anthropic-engineering": 365,
    "anthropic-docs-api": 180,
    "anthropic-docs-claude-code": 180,
    "anthropic-support-release-notes": 180,
}


@dataclass
class AuditSourceResult:
    key: str
    status: str
    item_count: int
    newest_published_at: str | None
    elapsed_ms: int
    error: str | None
    sample_titles: list[str]
    warnings: list[str]


class AuditSummary(TypedDict):
    total: int
    ok: int
    warning: int
    failed: int


class AuditSourceReport(TypedDict):
    key: str
    status: str
    item_count: int
    newest_published_at: str | None
    elapsed_ms: int
    error: str | None
    sample_titles: list[str]
    warnings: list[str]


async def _audit_one(config: SourceConfig) -> AuditSourceResult:
    started = perf_counter()
    warnings: list[str] = []
    try:
        items = await config.fetcher_cls().fetch()
        elapsed_ms = int((perf_counter() - started) * 1000)
        newest = _newest(items)
        if not items and config.key in _CANONICAL_REQUIRED:
            warnings.append("canonical source returned zero items")
        if newest and config.key in _REGULARLY_UPDATED:
            age_days = (datetime.now(tz=UTC) - newest).days
            threshold = _REGULARLY_UPDATED[config.key]
            if age_days > threshold:
                warnings.append(f"newest item is {age_days} days old")
        return AuditSourceResult(
            key=config.key,
            status="warning" if warnings else "ok",
            item_count=len(items),
            newest_published_at=newest.isoformat() if newest else None,
            elapsed_ms=elapsed_ms,
            error=None,
            sample_titles=[item.title for item in items[:3]],
            warnings=warnings,
        )
    except Exception as exc:
        return AuditSourceResult(
            key=config.key,
            status="failed",
            item_count=0,
            newest_published_at=None,
            elapsed_ms=int((perf_counter() - started) * 1000),
            error=_sanitize_error(exc),
            sample_titles=[],
            warnings=[],
        )


def _newest(items: list[NewsItem]) -> datetime | None:
    dated = [item.published_at for item in items if item.published_at is not None]
    if not dated:
        return None
    return max(dated)


async def run_audit(source_keys: list[str] | None = None) -> dict[str, object]:
    registry = SOURCE_REGISTRY
    if source_keys:
        requested = set(source_keys)
        registry = [config for config in registry if config.key in requested]
    results = await asyncio.gather(*[_audit_one(config) for config in registry])
    summary = {
        "total": len(results),
        "ok": sum(1 for result in results if result.status == "ok"),
        "warning": sum(1 for result in results if result.status == "warning"),
        "failed": sum(1 for result in results if result.status == "failed"),
    }
    return {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "summary": summary,
        "sources": [asdict(result) for result in results],
    }


def _print_table(report: dict[str, object]) -> None:
    print(f"Anthropic source audit ({report['timestamp']})")
    print("source                                status    items  newest                ms")
    print("-" * 78)
    sources = cast(list[AuditSourceReport], report["sources"])
    for source in sources:
        newest = source["newest_published_at"] or "-"
        print(
            f"{source['key']:<37} {source['status']:<9} "
            f"{source['item_count']:>5}  {newest[:19]:<19} {source['elapsed_ms']:>5}"
        )
        for warning in source["warnings"]:
            print(f"  warning: {warning}")
        if source["error"]:
            print(f"  error: {source['error']}")
    summary = cast(AuditSummary, report["summary"])
    print(
        f"\nsummary: {summary['ok']} ok, {summary['warning']} warning, "
        f"{summary['failed']} failed, {summary['total']} total"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live Anthropic source audit")
    parser.add_argument(
        "--sources",
        help="Comma-separated source keys to audit, e.g. anthropic-status,anthropic-engineering",
    )
    parser.add_argument("--json", dest="json_path", help="Write report JSON to this path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero when a canonical source fails or warns",
    )
    args = parser.parse_args()

    source_keys = args.sources.split(",") if args.sources else None
    report = asyncio.run(run_audit(source_keys))
    _print_table(report)

    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.strict:
        sources = cast(list[AuditSourceReport], report["sources"])
        bad = [
            source
            for source in sources
            if source["key"] in _CANONICAL_REQUIRED and source["status"] in {"failed", "warning"}
        ]
        if bad:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
