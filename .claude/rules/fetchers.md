---
paths:
  - "src/anthropic_news_mcp/fetchers/**"
  - "tests/test_fetchers/**"
---

# Fetcher rules

- Subclass `Fetcher` from `fetchers/base.py`. Set `source_key` as a **class variable** matching the `SourceConfig.key` you register in `config.py`.
- One async method: `fetch(self) -> list[NewsItem]`.
- **Raise** on transport errors (httpx exceptions, parse failures). Do **not** wrap in `try/except`. The retrieval layer catches, retries (tenacity), and sanitizes.
- Return `[]` for legitimately empty sources. Never return `None`.
- Use `http.get_client()` — never construct `httpx.AsyncClient(...)` directly. New host must be added to `_ALLOWED_FETCH_HOSTS` in `http.py` first.
- Set each `NewsItem.source_key == self.source_key`.
- UTC-aware datetimes only; `importance ∈ {1,2,3}`; `source_type` and `evidence_tier` match the values in the matching `SourceConfig`.
- Do not cache. Do not hold instance state across calls.
- Pair every new fetcher with: (a) frozen fixture in `tests/fixtures/<name>.<ext>`, (b) parser test in `tests/test_fetchers/test_<name>.py` using the existing monkeypatch pattern, (c) `SourceConfig(...)` entry in `_build_registry()` (imports inside the function to avoid circular imports).

Skill walkthrough: [.claude/skills/add-source.md](../skills/add-source.md).
