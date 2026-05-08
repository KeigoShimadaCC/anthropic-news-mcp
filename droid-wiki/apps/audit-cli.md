# Source-audit CLI

`anthropic-news-audit` is a small CLI that runs every fetcher live, reports per-source status, and exits nonzero in `--strict` mode if a canonical source fails or warns. It is intentionally separate from the offline tests and the offline eval — the audit makes real HTTP requests, so it's opt-in only.

## Purpose

Provide a fast, repeatable way to verify that every configured source is still reachable, returning items, and producing recently-dated content.

## Console script

```toml
[project.scripts]
anthropic-news-audit = "anthropic_news_mcp.audit:main"
```

## Usage

```bash
anthropic-news-audit                                              # all sources, table output
anthropic-news-audit --sources anthropic-status,anthropic-engineering
anthropic-news-audit --json evals/results/source_audit_$(date -u +%Y%m%dT%H%M%SZ).json
anthropic-news-audit --strict                                     # exit 1 on canonical source failure/warning
```

## Output

The CLI prints a fixed-width table to stdout:

```
Anthropic source audit (2026-05-08T07:30:00+00:00)
source                                status    items  newest                ms
------------------------------------------------------------------------------
anthropic-newsroom                    ok           15  2026-05-07T12:34:56  840
anthropic-status                      ok            3  2026-05-08T03:00:00  220
...

summary: 14 ok, 2 warning, 1 failed, 17 total
```

Each row carries source key, audit status, item count, newest published timestamp, and elapsed milliseconds. Warnings and errors print on continuation lines.

With `--json`, the same data is written to a file with this shape:

```json
{
  "timestamp": "...",
  "summary": {"total": 17, "ok": 14, "warning": 2, "failed": 1},
  "sources": [
    {
      "key": "anthropic-newsroom",
      "status": "ok",
      "item_count": 15,
      "newest_published_at": "...",
      "elapsed_ms": 840,
      "error": null,
      "sample_titles": ["...", "...", "..."],
      "warnings": []
    },
    ...
  ]
}
```

## Audit logic

`run_audit(source_keys)`:

1. Filter `SOURCE_REGISTRY` to the requested keys (or use the full registry).
2. `asyncio.gather(*[_audit_one(c) for c in registry])`.
3. Aggregate counts.

`_audit_one(config)`:

- Time the fetch with `perf_counter`.
- Catch every exception and return `failed` with a sanitized error.
- On success, check two warning conditions:
  - **Canonical sources returning zero items.** The `_CANONICAL_REQUIRED` set covers nine sources (newsroom, status, research, engineering, all the docs/api/apps/system-prompts/support release notes, and the economic index) — these should never legitimately be empty.
  - **Stale items.** The `_REGULARLY_UPDATED` map sets a max age in days per source: 180 days for newsroom, API docs, Claude Code docs, support release notes; 365 days for research and engineering. A newest-item age above the threshold becomes a warning.
- Return an `AuditSourceResult` with status (`ok`, `warning`, or `failed`), counts, and sample titles.

## Strict mode

`--strict` exits 1 if any source in `_CANONICAL_REQUIRED` ended in `failed` or `warning`. Use this in scheduled monitoring to alert on Anthropic source breakage.

## Errors

Errors run through `retrieval._sanitize_error`, the same redactor used by the live cache write path. Tokens, query strings, and Authorization headers never leak into audit output.

## Integration points

- **Reads:** `SOURCE_REGISTRY` from `config.py`, every fetcher class.
- **Calls:** Each fetcher's `fetch()` directly (no cache involvement).
- **Used by:** Operators verifying source health; ad hoc CI jobs (the GitHub Actions workflow `eval.yml` is a manual trigger and does not invoke the audit, but operators sometimes wire it into scheduled checks).

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/audit.py` | The full audit CLI (~187 lines) |
| `tests/test_audit.py` | Unit tests for `_audit_one` and the warning logic |

## Entry points for modification

- To add a new "must not be empty" source: add its key to `_CANONICAL_REQUIRED` in `audit.py`.
- To tighten / loosen the staleness threshold for a source: edit `_REGULARLY_UPDATED`.
- To add a new warning category: extend the `warnings.append(...)` calls inside `_audit_one`.
- To support an alternative output format (e.g. CSV): branch on a new CLI flag in `main()` and write the format from the existing `report` dict.
