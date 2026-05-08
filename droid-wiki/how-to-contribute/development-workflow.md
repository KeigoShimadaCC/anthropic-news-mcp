# Development workflow

The standard cycle: branch → code → test → PR → merge.

## Setup

```bash
git clone https://github.com/KeigoShimadaCC/anthropic-news-mcp
cd anthropic-news-mcp
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pre-commit install
.venv/bin/pre-commit install --hook-type pre-push
```

The two `pre-commit install` calls register both the per-commit hooks (lint, format, mypy) and the per-push hook (offline pytest suite).

## Branching

There's no enforced branch naming convention. Recent commits show a mix of `feat:`, `fix:`, `docs:`, `chore:`, `test:` prefixes; follow that style for commit messages. The default branch is `master` (per `git rev-parse --abbrev-ref HEAD` checking `master` ref existence).

## Adding a new source

The two-step recipe documented in the README and elsewhere:

### 1. Write the fetcher

Create `src/anthropic_news_mcp/fetchers/<name>.py`:

```python
from datetime import UTC, datetime

from ..http import get_client
from ..models import Category, DateConfidence, NewsItem, Source
from .base import Fetcher


class MyNewSourceFetcher(Fetcher):
    source_key = "my-new-source"

    async def fetch(self) -> list[NewsItem]:
        async with get_client() as client:
            resp = await client.get("https://example.com/feed.json")
            resp.raise_for_status()
        return [
            NewsItem(
                id=f"my-new-source-{entry['id']}",
                title=entry["title"],
                summary=entry.get("summary", "")[:400],
                url=entry["url"],
                source=Source.ANTHROPIC,  # or whichever family fits
                source_key=self.source_key,
                category=[Category.MODELS],
                published_at=datetime.fromisoformat(entry["published_at"]),
                date_confidence=DateConfidence.EXACT,
                importance=2,
            )
            for entry in resp.json().get("entries", [])
        ]
```

Rules to follow:

- Set `source_key` as a class variable matching the registry entry.
- Raise on HTTP errors. The retrieval layer catches and sanitizes.
- Return `[]` for empty sources.
- Use `get_client()` so the outbound host allowlist applies.
- IDs must be stable across fetches.

### 2. Register the source

Edit `src/anthropic_news_mcp/config.py` and add a `SourceConfig(...)` entry inside `_build_registry()`:

```python
from .fetchers.my_new_source import MyNewSourceFetcher  # inside _build_registry()

return [
    # ... existing entries ...
    SourceConfig(
        key="my-new-source",
        fetcher_cls=MyNewSourceFetcher,
        ttl_seconds=1800,
        default_categories=[Category.MODELS],
        description="My new source description for list_sources",
        source_type=SourceType.OFFICIAL,
        evidence_tier=EvidenceTier.HIGH,
    ),
]
```

Position the entry where you want it for tie-breaking — earlier entries win in trust-ranked dedup.

### 3. Allow the host

If the new source's host isn't already in `_ALLOWED_FETCH_HOSTS` in `src/anthropic_news_mcp/http.py`, add it. The response hook rejects any unlisted host.

### 4. Add a fixture and test

Save a real response from the source into `tests/fixtures/<name>.<ext>`:

```bash
curl -sSL "https://example.com/feed.json" -o tests/fixtures/my_new_source.json
```

Then add a parser test in `tests/test_fetchers/test_<name>.py`. Test the parser directly without HTTP:

```python
import json
from pathlib import Path

from anthropic_news_mcp.fetchers.my_new_source import MyNewSourceFetcher  # or expose a parse fn

FIXTURE = Path(__file__).parent.parent / "fixtures" / "my_new_source.json"


def test_parse_my_new_source() -> None:
    data = json.loads(FIXTURE.read_text())
    # call your parsing function or instantiate fetcher and inject the data
    ...
```

If your fetcher's parsing logic is intertwined with HTTP fetching, consider refactoring the parser into a module-level function so the test can call it on the fixture text directly.

### 5. Verify

```bash
.venv/bin/pytest tests/test_fetchers/test_my_new_source.py -v
.venv/bin/pytest tests/test_server.py::test_list_sources_returns_all -v
```

The second test asserts every registry entry round-trips through `list_sources` — it'll fail until the registry entry is correct.

### 6. Audit live (optional)

```bash
.venv/bin/anthropic-news-audit --sources my-new-source
```

This makes a live HTTP call to verify the source works in the wild. Skip if you're working offline.

## Adding a new tool

Edit `src/anthropic_news_mcp/server.py`. Define an async function decorated with `@mcp.tool(...)`:

```python
@mcp.tool(annotations=READ_ONLY, structured_output=True)
async def my_new_tool(
    foo: Annotated[str, Field(description="...")],
    limit: Annotated[int, Field(default=10, description="...")] = 10,
) -> dict[str, object]:
    """One-line summary.

    Detailed description and argument docs.

    Returns: ...
    """
    if not foo.strip():
        return _error("foo must not be blank.")
    parsed_limit, limit_error = _parse_limit(limit, default_max=100)
    if limit_error:
        return limit_error
    # Implement the tool logic, calling into research/retrieval/cache.
    ...
```

Use the existing `_parse_*` helpers and `_error(...)` envelope. Pick the right `ToolAnnotations` (`READ_ONLY`, `OPEN_WORLD_READ`, or `LOCAL_WRITE`).

Add a server integration test in `tests/test_server.py`:

```python
@pytest.mark.asyncio
async def test_my_new_tool() -> None:
    _seed()
    data = await _call("my_new_tool", {"foo": "bar"})
    assert "items" in data
```

## Pull request flow

1. Push your branch.
2. Open a PR against the default branch.
3. CI runs `lint-and-test` (lint, format, mypy, pytest, offline eval) and CodeQL.
4. The repo's target state requires PR approval and the two status checks before merge — see the README's "Branch protection target state" section.
5. Squash or rebase merge — the commit history shows tight, focused commits.

## Changelog

There's no separate `CHANGELOG.md`. The `git log` is the changelog. Use clear commit messages with a category prefix and a short summary.
