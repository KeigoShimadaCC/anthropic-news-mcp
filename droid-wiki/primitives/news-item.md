# News item

`NewsItem` is the canonical data type for every news, changelog, release, or community item in the system. Every fetcher returns `list[NewsItem]`, the cache stores `NewsItem`s, and every tool that returns items returns serialized `NewsItem`s.

Defined in `src/anthropic_news_mcp/models.py`.

## Schema

```python
class NewsItem(BaseModel):
    id: str
    title: str
    summary: str = ""
    url: HttpUrl
    source: Source
    source_key: str
    category: list[Category] = []
    published_at: datetime | None = None
    discovered_at: datetime = <now UTC>
    sort_at: datetime | None = None
    date_confidence: DateConfidence = DateConfidence.EXACT
    importance: Literal[1, 2, 3] = 1
    tags: list[str] = []
    author: str | None = None
    source_type: SourceType = SourceType.OFFICIAL
    evidence_tier: EvidenceTier = EvidenceTier.HIGH
    is_official: bool = True
```

## Field semantics

| Field | Notes |
|-------|-------|
| `id` | Stable identifier. Format `<source-prefix>-<stable-hash-or-native-id>`. Must be stable across fetches — used as the key in the `items` and `item_history` tables. |
| `title` | Free text. Untrusted external data. |
| `summary` | Short description, target ~400 chars. Untrusted. |
| `url` | Pydantic `HttpUrl` — validated as a URL. Used for trust-ranked dedup after canonicalization. |
| `source` | High-level source family enum (`anthropic`, `github`, `reddit`, `hackernews`). |
| `source_key` | Specific source registry key, e.g. `anthropic-newsroom`. |
| `category` | List of `Category` values. A single item can be in multiple categories. |
| `published_at` | Source-published timestamp when known. UTC. |
| `discovered_at` | Server-side discovery timestamp. UTC. Defaults to `now`. |
| `sort_at` | Used for ordering. Filled by `_fill_derived_fields` from `published_at` or `discovered_at`. |
| `date_confidence` | `exact`, `inferred`, or `unknown`. Auto-downgraded to `unknown` when `published_at` is missing. |
| `importance` | `Literal[1, 2, 3]` — not a free-form int. |
| `tags` | Source-specific tags (status indicators, GitHub labels, etc.). Untrusted. |
| `author` | Free text when known. Untrusted. |
| `source_type` | Trust class. Used for dedup ranking and `search_web_sources` filtering. |
| `evidence_tier` | Trust quality (`high`, `medium`, `low`). |
| `is_official` | Derived: `source_type in {OFFICIAL, DOCS}`. Set by `_fill_derived_fields`. |

## Derived fields

`_fill_derived_fields` runs as a `model_validator(mode="after")`:

```python
if self.sort_at is None:
    self.sort_at = self.published_at or self.discovered_at
if self.published_at is None and self.date_confidence == DateConfidence.EXACT:
    self.date_confidence = DateConfidence.UNKNOWN
self.is_official = self.source_type in {SourceType.OFFICIAL, SourceType.DOCS}
```

This means callers don't have to remember to populate `sort_at` or `is_official` — set the primary fields and the validator fills the rest.

## Serialization shape

`item.model_dump(mode="json")` produces the JSON shape clients see:

```json
{
  "id": "newsroom-abc123",
  "title": "Claude 4 release",
  "summary": "Anthropic released Claude 4 ...",
  "url": "https://www.anthropic.com/news/claude-4",
  "source": "anthropic",
  "source_key": "anthropic-newsroom",
  "category": ["models"],
  "published_at": "2026-05-08T12:00:00Z",
  "discovered_at": "2026-05-08T12:30:00Z",
  "sort_at": "2026-05-08T12:00:00Z",
  "date_confidence": "exact",
  "importance": 3,
  "tags": [],
  "author": null,
  "source_type": "official",
  "evidence_tier": "high",
  "is_official": true
}
```

## Enums

All defined in `src/anthropic_news_mcp/models.py` as `StrEnum` so values serialize as strings.

### `Category`

`models`, `claude-code`, `research`, `policy`, `business`, `community`, `ops`, `engineering`, `economics`.

A single item can have multiple categories. The `categories` filter on tools matches if any source category appears in the filter list.

### `Source`

`anthropic`, `github`, `reddit`, `hackernews` — the high-level family. Multiple `source_key`s map to the same `source`.

### `SourceType`

`official`, `docs`, `github`, `community`. Drives dedup ranking and `search_web_sources` filtering.

### `EvidenceTier`

`high`, `medium`, `low`. Drives evidence excerpt provenance and dedup tie-breaking.

### `SourceStatus`

`live`, `cache`, `stale`, `down`, `not_fetched`. Returned in `SourceHealth.status`.

### `DateConfidence`

`exact`, `inferred`, `unknown`. The model validator auto-downgrades to `unknown` when `published_at` is missing.

### `ClaimSupport`

`strong_support`, `weak_support`, `unsupported`, `needs_review`. Returned by `evaluate_claims`.

## ID conventions

The ID prefix tells you which fetcher produced the item:

| Prefix | Source |
|--------|--------|
| `newsroom-...` | newsroom listing |
| `research-...` | research listing |
| `engineering-...` | engineering listing |
| `economic-index-...`, `economic-research-...` | economic index |
| `business-infra-...` | business-infrastructure filter |
| `trust-policy-...` | trust-policy filter |
| `status-rollup-...`, `status-incident-...`, `status-maintenance-...` | status |
| `docs-cc-<version>` | Claude Code CHANGELOG |
| `docs-api-<slug>` | API release notes |
| `docs-claude-apps-<slug>` | Claude Apps docs |
| `docs-system-prompts-<slug>` | system prompts docs |
| `support-release-notes-<slug>` | support release notes |
| `github-release-<id>` | GitHub releases |
| `github-event-<id>` | GitHub org events |
| `github-issue-<repo>-<number>` | GitHub issues / PRs |
| `hn-<objectID>` | Hacker News |
| `reddit-<post_id>` | Reddit |

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/models.py` | All models and enums (~180 lines) |
| `src/anthropic_news_mcp/cache.py` | Stores `NewsItem` payload as JSON in two tables |
