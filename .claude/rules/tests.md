---
paths:
  - "tests/**"
  - "evals/**"
---

# Test & eval rules

- **Offline only.** No `httpx` calls hit the network. Fetcher tests monkeypatch `httpx.AsyncClient` to return a frozen fixture from `tests/fixtures/`.
- Cache/server tests get a fresh SQLite path via the autouse `set_db_path(tmp_path/...)` fixture. Do not write to `~/.cache/...` from tests.
- FastMCP integration tests call `await mcp.call_tool(name, args)`. Return shape on FastMCP 1.27 is `(list[content], raw_dict)` — read `result[0][0].text` for the JSON.
- Pytest config: `asyncio_mode = "auto"`. Mark async fixtures only when you need a non-default behavior. Coverage gate is `--cov-fail-under=80`.
- When fixing a parser regression, capture the failing live page with `curl -s "<url>" > tests/fixtures/<key>.html`, then add an assertion that fails on the old code and passes on the fix.
- Offline eval: `python evals/run_offline_eval.py` — deterministic, seeded SQLite cache, no API key. Treat this as a CI gate.
- Paid LLM eval: `python evals/run_eval.py` — requires `ANTHROPIC_API_KEY`, costs ~$0.15, opt-in only. Not a CI gate.
- Never mock away the real bug. If a test passes only because of a mock, freeze a fixture and remove the mock.
- `mypy.ini` excludes `evals/`; do not assume strict typing in `evals/` modules.
