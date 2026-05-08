# Source config and registry

`SourceConfig` is the dataclass that describes one source: which fetcher produces its items, how long its results are fresh, what categories it defaults to, what trust tier it sits in. The frozen list `SOURCE_REGISTRY` enumerates every configured source.

Both live in `src/anthropic_news_mcp/config.py`.

## `SourceConfig`

```python
@dataclass(frozen=True)
class SourceConfig:
    key: str
    fetcher_cls: "type[Fetcher]"
    ttl_seconds: int
    default_categories: list[Category] = []
    enabled: bool = True
    description: str = ""
    source_type: SourceType = SourceType.OFFICIAL
    evidence_tier: EvidenceTier = EvidenceTier.HIGH
```

| Field | Purpose |
|-------|---------|
| `key` | Stable identifier used as the source key in items, cache rows, and tool arguments |
| `fetcher_cls` | Concrete `Fetcher` subclass to instantiate when refreshing |
| `ttl_seconds` | Per-source freshness window |
| `default_categories` | Categories applied to items if the fetcher doesn't override |
| `enabled` | Set to `False` to keep the source in the registry but skip it during refresh |
| `description` | Human-readable description, surfaced in `list_sources` |
| `source_type` | `OFFICIAL`, `DOCS`, `GITHUB`, or `COMMUNITY` |
| `evidence_tier` | `HIGH`, `MEDIUM`, or `LOW` |

## `SOURCE_REGISTRY`

The frozen list returned by `_build_registry()`:

- Order matters. The `_representative_key` tuple includes `-registry_order` as the final tie-breaker, so earlier entries win when source type, evidence tier, and other ranking fields are equal.
- The function imports fetcher classes inside its body to avoid circular imports. New fetcher imports must follow the same pattern.

The full list is documented in [Sources](../sources/index.md).

## `SourceHealth`

The runtime counterpart to `SourceConfig`:

```python
class SourceHealth(BaseModel):
    key: str
    status: SourceStatus
    fetched_at: datetime
    expires_at: datetime
    item_count: int
    error: str | None = None
```

`SourceHealth` is what the `get_source_health` tool and `anthropic-news://health` resource return. The retrieval layer rewrites `status` from `LIVE` (just refreshed) to `CACHE` (served from a fresh snapshot) when a cached row is returned without a refresh.

## How registry entries flow through the system

```mermaid
graph LR
    Config[SourceConfig in registry]
    Fetcher[fetcher_cls.fetch]
    Items[list[NewsItem]]
    Snapshot[(source_snapshots row)]
    Health[SourceHealth]
    Tool[list_sources tool]

    Config --> Fetcher
    Config --> Tool
    Fetcher --> Items
    Items --> Snapshot
    Snapshot --> Health
```

A few touchpoints worth knowing:

- `list_sources` tool surfaces every entry's key, description, enabled flag, default categories, TTL, source type, and evidence tier. Adding a new entry adds it to `list_sources` automatically — there's no separate registration step.
- The retrieval layer trusts `enabled`. Disabled sources are skipped entirely.
- The audit CLI (`anthropic-news-audit`) iterates the same registry. Adding a new source automatically adds it to the audit.

## Adding a new source: registry checklist

1. Pick a stable `key`. Convention: kebab-case, prefixed by the source family. Examples: `anthropic-newsroom`, `github-releases`, `hn-anthropic`.
2. Decide on the `source_type` and `evidence_tier`. Use `OFFICIAL/HIGH` for first-party content, `DOCS/HIGH` for first-party docs, `GITHUB/MEDIUM` for GitHub APIs, `COMMUNITY/LOW` for third-party discussion.
3. Pick a TTL. Status-like sources should be 5 min; high-churn sources 30 min; release-note pages 60 min; long-tail sources 120+ min.
4. Add a `SourceConfig(...)` entry to `_build_registry()` in `src/anthropic_news_mcp/config.py`. Place it where you want it for tie-breaking.
5. Verify `tests/test_server.py::test_list_sources_returns_all` still passes — the test asserts the registry's keys round-trip through `list_sources`.

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/config.py` | `SourceConfig` and `SOURCE_REGISTRY` (~190 lines) |
| `src/anthropic_news_mcp/models.py` | `SourceHealth`, `SourceType`, `EvidenceTier`, `SourceStatus` |
