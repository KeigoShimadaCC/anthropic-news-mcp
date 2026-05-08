# Data models

Full Pydantic schemas as defined in `src/anthropic_news_mcp/models.py`. Every type listed here is a `pydantic.BaseModel` (or a `StrEnum` for the closed value sets). All `datetime` fields are timezone-aware UTC.

## `NewsItem`

```python
class NewsItem(BaseModel):
    id: str                                 # "<source-prefix>-<stable-hash-or-native-id>"
    title: str
    summary: str = ""                       # max ~400 chars by convention
    url: HttpUrl
    source: Source                          # ANTHROPIC | GITHUB | REDDIT | HACKERNEWS
    source_key: str                         # e.g. "anthropic-newsroom"
    category: list[Category] = []
    published_at: datetime | None = None
    discovered_at: datetime = <now UTC>
    sort_at: datetime | None = None         # filled by validator
    date_confidence: DateConfidence = EXACT # auto-downgraded to UNKNOWN if no published_at
    importance: Literal[1, 2, 3] = 1
    tags: list[str] = []
    author: str | None = None
    source_type: SourceType = OFFICIAL
    evidence_tier: EvidenceTier = HIGH
    is_official: bool = True                # derived: source_type in {OFFICIAL, DOCS}
```

## `SourceConfig`

```python
@dataclass(frozen=True)
class SourceConfig:
    key: str
    fetcher_cls: type[Fetcher]
    ttl_seconds: int
    default_categories: list[Category] = []
    enabled: bool = True
    description: str = ""
    source_type: SourceType = OFFICIAL
    evidence_tier: EvidenceTier = HIGH
```

(Defined in `src/anthropic_news_mcp/config.py`, not `models.py`.)

## `SourceHealth`

```python
class SourceHealth(BaseModel):
    key: str
    status: SourceStatus     # LIVE | CACHE | STALE | DOWN | NOT_FETCHED
    fetched_at: datetime
    expires_at: datetime
    item_count: int
    error: str | None = None # sanitized, ≤200 chars
```

## `ContentDetail`

```python
class ContentDetail(BaseModel):
    item_id: str
    url: HttpUrl
    normalized_text: str    # capped at _MAX_STORED_CHARS = 50_000
    retrieved_at: datetime
    content_hash: str       # sha256 of normalized_text
    content_type: str       # response Content-Type, primary type only
    truncated: bool = False
    warnings: list[str] = []
```

## `EvidenceExcerpt`

```python
class EvidenceExcerpt(BaseModel):
    evidence_id: str        # sha256(item.id + ":" + content_hash + ":" + start + ":" + end)
    item_id: str
    url: HttpUrl
    title: str
    source_key: str
    source_type: SourceType
    evidence_tier: EvidenceTier
    text: str               # ~900-char window
    start_char: int
    end_char: int
    retrieved_at: datetime
    content_hash: str
```

## `DedupCluster`

```python
class DedupCluster(BaseModel):
    cluster_id: str         # sha256(canonical_url + sorted(item_ids))
    representative_item_id: str
    item_ids: list[str]
    canonical_url: str
    evidence_tier: EvidenceTier
```

## `TimelineGroup`

```python
class TimelineGroup(BaseModel):
    date: str               # "YYYY-MM-DD"
    items: list[NewsItem]
    clusters: list[DedupCluster] = []
```

## `ResearchSession`

```python
class ResearchSession(BaseModel):
    session_id: str         # uuid4().hex
    title: str
    topic: str | None = None
    filters: dict[str, object] = {}
    created_at: datetime
    updated_at: datetime
```

## `ResearchNote`

```python
class ResearchNote(BaseModel):
    note_id: str            # uuid4().hex
    session_id: str
    text: str
    evidence_ids: list[str] = []
    follow_up: bool = False
    created_at: datetime
```

## `ResearchReport`

```python
class ResearchReport(BaseModel):
    report_id: str          # uuid4().hex
    session_id: str
    title: str
    markdown: str
    evidence_ids: list[str] = []
    created_at: datetime
```

## `ClaimEvaluationResult`

```python
class ClaimEvaluationResult(BaseModel):
    claim: str
    support: ClaimSupport   # STRONG | WEAK | UNSUPPORTED | NEEDS_REVIEW
    evidence: list[EvidenceExcerpt] = []
    reason: str
```

## Enums

### `Category` (StrEnum)

`models`, `claude-code`, `research`, `policy`, `business`, `community`, `ops`, `engineering`, `economics`

### `Source` (StrEnum)

`anthropic`, `github`, `reddit`, `hackernews`

### `SourceType` (StrEnum)

`official`, `docs`, `github`, `community`

### `EvidenceTier` (StrEnum)

`high`, `medium`, `low`

### `SourceStatus` (StrEnum)

`live`, `cache`, `stale`, `down`, `not_fetched`

### `DateConfidence` (StrEnum)

`exact`, `inferred`, `unknown`

### `ClaimSupport` (StrEnum)

`strong_support`, `weak_support`, `unsupported`, `needs_review`

## SQLite tables

For storage layout, see [Cache system](../systems/cache.md). The mapping:

| Pydantic model | SQLite table |
|----------------|--------------|
| `NewsItem` | `items` (per-row) and `source_snapshots.items_json` (bulk) |
| `SourceHealth` | `source_snapshots` |
| `ContentDetail` | `content_details` |
| `EvidenceExcerpt` | `evidence_excerpts` |
| `ResearchSession` | `research_sessions` |
| `ResearchNote` | `research_notes` |
| `ResearchReport` | `research_reports` |
| `DedupCluster` | (not persisted; computed per call) |
| `TimelineGroup` | (not persisted; computed per call) |
| `ClaimEvaluationResult` | (not persisted; computed per call) |
