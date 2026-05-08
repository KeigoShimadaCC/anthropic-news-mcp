# Testing

Every test runs offline. The full suite (146+ tests) finishes in well under a minute.

## Running tests

```bash
.venv/bin/pytest -q                                    # quiet, all tests
.venv/bin/pytest tests/ -v                             # verbose, all tests
.venv/bin/pytest tests/test_cache.py -v                # one file
.venv/bin/pytest tests/test_server.py::test_ping -v    # one test
```

`pyproject.toml` configures pytest:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

`asyncio_mode = "auto"` means async test functions don't need an explicit `@pytest.mark.asyncio` decorator. Most tests still use the decorator for clarity.

## Test layout

```
tests/
├── fixtures/                    # frozen HTTP responses
├── test_audit.py                # source-audit CLI
├── test_cache.py                # SQLite cache (~566 lines)
├── test_content.py              # content extraction and excerpts
├── test_eval_harness.py         # offline eval harness sanity
├── test_fetchers/               # per-source parser tests
│   ├── test_community.py        # HN + Reddit
│   ├── test_docs.py             # docs.claude.com release notes
│   ├── test_github.py           # all GitHub fetchers
│   ├── test_newsroom.py         # newsroom listing
│   └── test_official.py         # research, engineering, status
├── test_http.py                 # shared HTTP client + host allowlist
├── test_remote.py               # remote ASGI: auth, middleware
├── test_research.py             # research subsystem
├── test_retrieval.py            # retrieval layer dedup, error handling
└── test_server.py               # server integration via FastMCP.call_tool
```

## Cache isolation

`test_cache.py` and `test_server.py` use an `autouse` fixture to point the cache at a fresh `tmp_path`:

```python
@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path) -> None:
    cache_mod.set_db_path(tmp_path / "test.db")
    yield
    cache_mod.set_db_path(None)
```

Production code never calls `set_db_path`; it's reserved for tests and the eval harness's `seed.py`.

## Server integration tests

FastMCP 1.27 exposes an in-process `await mcp.call_tool(name, args)` API that returns a `(list[content], raw_dict)` tuple. The test helper unwraps it:

```python
async def _call(tool: str, args: dict) -> dict:
    from anthropic_news_mcp.server import mcp

    result = await mcp.call_tool(tool, args)
    if isinstance(result, tuple):
        content_list, _ = result
        text = content_list[0].text
    elif isinstance(result, list):
        text = result[0].text if hasattr(result[0], "text") else str(result[0])
    elif hasattr(result, "content"):
        text = result.content[0].text
    else:
        text = str(result)
    return json.loads(text)
```

This avoids the overhead of spinning up a subprocess per test. The eval harness uses the same approach for the same reason.

## Frozen fixtures

`tests/fixtures/` holds real HTTP responses captured at a known good moment. Fixture sizes range from 92 bytes (`status_operational.json`) to 990 KB (`docs_api.html`). Fixture file names match the source they came from:

| Fixture | Source |
|---------|--------|
| `newsroom.html`, `newsroom_filters.html` | Anthropic newsroom listing |
| `research.html`, `engineering.html` | Anthropic research/engineering listings |
| `status_operational.json`, `status_incidents.json`, `status_scheduled.json` | Statuspage endpoints |
| `docs_api.html` | platform.claude.com API release notes |
| `docs_claude_code.html`, `docs_claude_code_raw.md` | Claude Code CHANGELOG (rendered + raw) |
| `docs_claude_apps.html`, `docs_system_prompts.html`, `support_release_notes.html` | docs.claude.com / support release notes |
| `github_releases.json`, `github_events.json`, `github_events_synthetic.json` | GitHub API responses |
| `hackernews.json` | HN Algolia search response |
| `reddit_claudeai.json`, `reddit_anthropic.json` | Reddit hot.json responses |

When you add a new source, capture a fixture that's representative — include the same shapes the live API returns (with and without summaries, with and without dates, etc.).

## Mocking convention

Tests don't mock HTTP at the `httpx` level. Instead, parser logic is exposed as module-level functions that take strings or dicts directly:

```python
def _parse_newsroom_html(html: str) -> list[NewsItem]: ...
```

Test calls `_parse_newsroom_html(FIXTURE_PATH.read_text())` directly. This avoids `respx`/`httpretty` complexity and keeps tests fast.

A small number of tests do exercise the live HTTP path (e.g. `test_http.py` checks the response-host allowlist). Those tests use a real `httpx.AsyncClient` and a small in-process server when needed.

## Async test pattern

Most tests use:

```python
@pytest.mark.asyncio
async def test_something() -> None:
    data = await _call("ping", {})
    assert data["status"] == "ok"
```

`asyncio_mode = "auto"` in pyproject.toml means the decorator is technically optional, but using it explicitly makes IDE introspection happier.

## Eval harness sanity

`test_eval_harness.py` exercises the offline eval harness against the seed cache. This protects the eval harness itself from regressions — it ensures `seed_eval_cache(...)` produces a cache that the offline cases can run against.

## CI failure to test count

`tests/test_server.py::test_list_sources_returns_all` asserts that the registry's keys round-trip through `list_sources` exactly. If you add a registry entry without updating any tests, this test catches it. The README claims "146+ tests" because the count moves with each feature commit; the assertion is on completeness, not the absolute number.

## Type and lint

Tests are not currently type-checked under `mypy --strict` (the strict run is scoped to `src/`). Tests do still need to pass `ruff check`. Use type hints liberally — they make tests easier to refactor.

## Common test failure patterns

- **`set_db_path` left dangling.** If a test forgets to reset the cache path, subsequent tests pick up the stale path. The `autouse` fixture's `yield` block calls `set_db_path(None)` to reset.
- **Async test missing `await`.** `pytest-asyncio` will silently report success on a coroutine that was never awaited. Always `await` async helpers.
- **Pydantic validation errors.** Adding a required field to `NewsItem` or another model breaks every existing test that constructs the type. Default new fields when possible.
