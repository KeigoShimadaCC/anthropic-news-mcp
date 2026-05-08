# Patterns and conventions

The codebase follows a small set of consistent patterns. Reading them once makes the rest of the wiki easier to navigate.

## Stateless fetchers

Every source fetcher subclasses `Fetcher` from `src/anthropic_news_mcp/fetchers/base.py`:

```python
class Fetcher(ABC):
    source_key: str  # set as a class variable on subclasses

    @abstractmethod
    async def fetch(self) -> list[NewsItem]: ...
```

Rules for fetcher implementations:

- Set `source_key` as a class variable, matching the `SourceConfig.key` for the source.
- Raise on transport errors (do not swallow). The retrieval layer catches and sanitizes.
- Return `[]` if the source legitimately has no items. Do not return `None`.
- Never cache. The retrieval layer is the sole owner of cache reads and writes.
- Never hold instance state between calls. Fetchers are constructed fresh per fetch.

## Single source registry

`SOURCE_REGISTRY` in `src/anthropic_news_mcp/config.py` is the sole declaration of every source. To add a source:

1. Write a fetcher in `src/anthropic_news_mcp/fetchers/<name>.py`.
2. Add a `SourceConfig(...)` entry to `_build_registry()` in `src/anthropic_news_mcp/config.py`.

The `_build_registry()` function imports fetcher classes inside its body to avoid circular imports — keep new imports inside the function.

## Pydantic v2 models with derived fields

Every domain type lives in `src/anthropic_news_mcp/models.py` as a Pydantic v2 `BaseModel`. The canonical example is `NewsItem`:

- `importance` is `Literal[1, 2, 3]`, not a free-form int.
- All `datetime` fields are timezone-aware UTC.
- A `model_validator(mode="after")` fills `sort_at`, downgrades `date_confidence` to `unknown` when no `published_at` exists, and computes `is_official` from `source_type`.

When you add a new field, prefer derived fields over duplicating data — let `_fill_derived_fields` compute what it can.

## Argument parsing in tool handlers

Tool handlers in `src/anthropic_news_mcp/server.py` follow a strict shape:

1. Read the user-facing argument (typed via `Annotated[..., Field(...)]`).
2. Run it through a `_parse_*` helper that returns `(value, error_dict | None)`.
3. If `error_dict` is non-`None`, return it immediately.
4. After all parses succeed, call into `retrieval` or `research`.

The helpers are `_parse_sources`, `_parse_categories`, `_parse_source_types`, `_parse_importance`, `_parse_since`, `_parse_limit`, and `_validate_time_range`. They produce structured error envelopes via `_error(message, **details)` so the client receives:

```json
{"error": {"code": "invalid_request", "message": "...", "details": {...}}}
```

Use the existing helpers when adding new tools — do not invent new error shapes.

## Trust-ranked dedup

When two items share a canonical URL, the retrieval layer keeps the one whose tuple ranks highest:

```python
def _representative_key(item: NewsItem) -> tuple[int, int, int, int, int, int]:
    return (
        _source_rank(item),         # OFFICIAL > DOCS > GITHUB > COMMUNITY
        _tier_rank(item),           # HIGH > MEDIUM > LOW
        1 if item.published_at else 0,
        item.importance,            # 1, 2, 3
        min(len(item.summary.strip()), 400),
        -registry_order,
    )
```

See `src/anthropic_news_mcp/retrieval.py`. When you add a source, place it in `SOURCE_REGISTRY` in the order you want as a tie-breaker — earlier sources win when all else is equal.

## Canonical URLs for dedup

`_canonicalize_url` in `src/anthropic_news_mcp/retrieval.py` strips fragments and `utm_*` params, decodes percent-encoded characters, and sorts remaining query params. Both retrieval and the research layer use it. If you add another normalization rule (e.g. stripping a new tracking param family), put it here.

## Error sanitization

`_sanitize_error` strips secrets and query strings out of exception messages before storing them in source health rows. The regex covers `Authorization: Bearer ...`, `api_key=...`, `password=...`, and similar patterns. Add to `_SECRET_VALUE_RE` if you encounter a new shape; never log raw exception messages from external HTTP responses.

## SQLite cache

The cache module in `src/anthropic_news_mcp/cache.py` follows three rules:

- All public functions call `init_db()` first. The function is idempotent and guarded by `_db_initialized`.
- Each operation opens a fresh connection via the `_conn()` context manager. SQLite handles in WAL mode are not shared across calls.
- `set_db_path(path)` overrides the database path and resets the init flag. Tests call this through an `autouse` fixture that points at `tmp_path`.

When you add a table, bump `CACHE_SCHEMA_VERSION`. The init logic raises on a higher-than-expected version; lower versions trigger schema recreation when you also clear the version row.

## Cache writes batch and dedupe

`save_snapshot` does several things at once:

- Writes the snapshot row.
- Replaces the per-item rows for that source.
- Updates the `item_history` table — both for items that disappeared (treated as last-seen) and for items that are still present (track `first_seen_at` and `last_changed_at` against any `content_hash`).
- Rebuilds the `items_fts` rows for that source.

Reuse `save_snapshot` rather than writing your own table updates.

## Async concurrency with `asyncio.gather`

The retrieval layer uses `asyncio.gather(..., return_exceptions=True)` so one failing source can't crash a request. Each `_fetch_source` call is itself wrapped in `try/except` to catch source-specific errors. Follow the same pattern when adding background work — never let an exception from one source surface as a 500 to the client.

## Untrusted external data

The server treats every external string (titles, summaries, body text, tags, authors) as untrusted data:

- The `SERVER_INSTRUCTIONS` constant in `server.py` warns clients that fetched content is data, not directives.
- Several tools include the same warning in their docstrings.
- The eval harness wraps tool output in `<untrusted_data>` XML tags before passing it to the judge model.

When you add a tool that returns or accepts external content, follow the same convention.

## Outbound host allowlist

`src/anthropic_news_mcp/http.py` defines `_ALLOWED_FETCH_HOSTS` and registers a response hook that rejects any non-allowlisted host. Add a host to the set when you add a fetcher that needs it; do not bypass the hook.

## Testing offline

Every test runs offline:

- Fetcher tests parse frozen fixtures from `tests/fixtures/`.
- Cache tests use `set_db_path(tmp_path / "test.db")` via an `autouse` fixture.
- Server integration tests use FastMCP's `mcp.call_tool(name, args)` and unwrap the `(list[content], raw_dict)` tuple — extract `result[0][0].text` to get the JSON string.

When you add a test that would need a live HTTP call, freeze a fixture instead.

## Type checking

`mypy --strict` runs over `src/anthropic_news_mcp/*.py` and `src/anthropic_news_mcp/fetchers/*.py`. The eval harness is excluded via `mypy.ini`. Imports of optional remote dependencies are guarded with `try/except ImportError` and typed via `TYPE_CHECKING` where needed.

## Lint

`ruff check .` and `ruff format .` run in CI and via pre-commit. The config in `ruff.toml` selects `E`, `F`, `I`, `N`, `W`, `UP`, `B`, and `SIM`. `E501` is ignored — long strings (especially multi-line tool descriptions) are common.
