# Skill: Add a New News Source

Use this skill when the user asks to add a new Anthropic-related news source to the MCP server.

## Context

Sources are fetchers that scrape or parse a specific URL and return `NewsItem` objects.
All fetching is stateless and async. All tests must be offline (frozen fixtures only).

## Step-by-step

### 1. Create the fetcher

Create `src/anthropic_news_mcp/fetchers/<source_name>.py`:

```python
import httpx
from ..models import NewsItem
from .base import Fetcher

SOURCE_KEY = "anthropic-<source_name>"

class <SourceName>Fetcher(Fetcher):
    source_key = SOURCE_KEY

    async def fetch(self) -> list[NewsItem]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = client.get("https://example.com/feed")
            resp.raise_for_status()
        # parse resp.text / resp.json() into NewsItem objects
        ...
```

Rules:
- `source_key` must be a class variable (string), format: `anthropic-<name>`
- Raise on transport errors (let `retrieval.py` handle retry + fallback)
- Return `[]` on empty source
- Each `NewsItem.source_key` must equal `self.source_key`
- All `datetime` fields must be UTC-aware
- `importance` must be `Literal[1, 2, 3]`

### 2. Register the source

In `src/anthropic_news_mcp/config.py`, add a `SourceConfig` entry inside `_build_registry()`:

```python
from .fetchers.<source_name> import <SourceName>Fetcher

SourceConfig(
    key="anthropic-<source_name>",
    fetcher_cls=<SourceName>Fetcher,
    description="Brief description shown in list_sources.",
    ttl_seconds=3600,          # cache TTL
    default_categories=[Category.MODELS],  # choose from models.Category
    source_type=SourceType.OFFICIAL,       # OFFICIAL | DOCS | GITHUB | COMMUNITY
    evidence_tier=EvidenceTier.HIGH,       # HIGH | MEDIUM | LOW
    enabled=True,
),
```

### 3. Capture a fixture

Run the fetcher against the live URL and save the response:

```bash
curl -s "https://example.com/feed" > tests/fixtures/<source_name>.html
# or .json for JSON APIs
```

### 4. Write a parser unit test

Create `tests/test_fetchers/test_<source_name>.py`:

```python
import pytest
from pathlib import Path
from anthropic_news_mcp.fetchers.<source_name> import <SourceName>Fetcher

FIXTURE = Path(__file__).parent.parent / "fixtures" / "<source_name>.html"

@pytest.mark.asyncio
async def test_parse(monkeypatch):
    html = FIXTURE.read_text()
    # monkeypatch httpx to return the fixture
    ...
    fetcher = <SourceName>Fetcher()
    items = await fetcher.fetch()
    assert len(items) > 0
    for item in items:
        assert item.source_key == "<source_name>"
        assert item.url
        assert item.title
```

See `tests/test_fetchers/` for existing examples of the monkeypatch pattern.

### 5. Verify

```bash
.venv/bin/pytest tests/test_fetchers/test_<source_name>.py -v
.venv/bin/mypy --strict src/anthropic_news_mcp/fetchers/<source_name>.py
.venv/bin/ruff check src/anthropic_news_mcp/fetchers/<source_name>.py
```

## Checklist

- [ ] Fetcher file created in `src/anthropic_news_mcp/fetchers/`
- [ ] `source_key` class variable set
- [ ] Raises on transport errors
- [ ] `SourceConfig` added to `_build_registry()` in `config.py`
- [ ] Fixture saved in `tests/fixtures/`
- [ ] Unit test passes offline
- [ ] `mypy --strict` passes
- [ ] `ruff check` passes
