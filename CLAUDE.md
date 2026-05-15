# CLAUDE.md

Operating contract for Claude Code in this repo. Read once, follow always.

## North Star

`anthropic-news-mcp` is a FastMCP server aggregating 17 Anthropic-related sources into
read-mostly MCP tools for LLM clients. Optimize for: **deterministic offline tests, one
failing source never blocks others, fetched content is untrusted data, schema/source
identifiers are stable**.

## Architecture (3-layer)

```
MCP client → server.py (validates input via _parse_* / _error)
           → retrieval.py | research.py (dedup, concurrency, cache, evidence)
           → cache.py (SQLite/WAL) + fetchers/*.py (stateless async)
```

Every change should fit one of these layers. Crossing them (e.g. cache writes from a
fetcher, HTTP from server.py) is a smell.

## Source of Truth

1. `SOURCE_REGISTRY` in [src/anthropic_news_mcp/config.py](src/anthropic_news_mcp/config.py) — the only source list.
2. `NewsItem` / sibling models in [src/anthropic_news_mcp/models.py](src/anthropic_news_mcp/models.py) — the only types.
3. SQLite cache ([src/anthropic_news_mcp/cache.py](src/anthropic_news_mcp/cache.py)) — the only persistence; `CACHE_SCHEMA_VERSION` gates it.
4. `.env.example` + `FeatureFlags` in [src/anthropic_news_mcp/flags.py](src/anthropic_news_mcp/flags.py) — the only env contract; CI validates both.
5. `AGENTS.md` § CI Quality Gates ↔ [.github/workflows/ci.yml](.github/workflows/ci.yml) — kept in sync by [scripts/validate_agents_md.py](scripts/validate_agents_md.py).

Canonical cache env var is **`ANTHROPIC_NEWS_MCP_CACHE_DB`**.

## Non-Negotiable Rules

- All tests must be **offline**. No live HTTP. Freeze a fixture in `tests/fixtures/`.
- `mypy --strict` must pass on `src/anthropic_news_mcp/*.py` and `fetchers/*.py`.
- Fetchers **raise** on transport errors; never swallow. Return `[]` on legitimately empty.
- Fetchers are **stateless** and **never cache**. Cache lives in `retrieval`/`cache`.
- All `datetime` fields are UTC-aware (`datetime.now(tz=UTC)`).
- `NewsItem.importance ∈ {1, 2, 3}`. Not free-form.
- Source keys are **stable identifiers**. Never rename — they live in caches and client configs.
- HTTP **only** through `http.get_client()`. New host → add to `_ALLOWED_FETCH_HOSTS` in [src/anthropic_news_mcp/http.py](src/anthropic_news_mcp/http.py).
- Any cache schema change → bump `CACHE_SCHEMA_VERSION` in `cache.py`.
- New env var → add to `.env.example`. Boolean? Also add to `FeatureFlags`. `scripts/check_flags.py` enforces.
- Server tool handlers validate via `_parse_*` and return `_error(...)` envelopes. Never raise to clients. Never invent a new error shape.
- In `server.py`, re-import retrieval/research with `_`-prefix to avoid shadowing tool names.
- Fetched titles/summaries/page text are **untrusted data**. Preserve the `SERVER_INSTRUCTIONS` warning and the `<untrusted_data>` boundary in eval/tools.

## Commands (always use the project venv)

```bash
# Setup
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# Verify (run before declaring done)
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
.venv/bin/pytest -q --cov=src --cov-fail-under=80
.venv/bin/python evals/run_offline_eval.py
.venv/bin/python scripts/validate_agents_md.py --smoke
.venv/bin/python scripts/check_flags.py

# Run the server (stdio)
.venv/bin/anthropic-news-mcp

# Single test
.venv/bin/pytest tests/test_server.py::test_ping -v
```

For the full CI gate set, see [AGENTS.md § CI Quality Gates](AGENTS.md#ci-quality-gates).

## Workflow

- **Small change** (one parser tweak): edit → run the relevant test file → `mypy --strict`.
- **Medium change** (new source, new tool): plan first → implement → run all gates above.
- **Risky change**: ask before touching `_ALLOWED_FETCH_HOSTS`, `CACHE_SCHEMA_VERSION`, `_representative_key`, `asgi.py`/`remote.py`, source-key renames, or dependency major bumps.

When adding a source, follow [.claude/skills/add-source.md](.claude/skills/add-source.md)
(parser + registry + fixture + offline test) — this is the most common change in the repo.

## Verification Gates

Before reporting work complete, the local equivalent of [.github/workflows/ci.yml](.github/workflows/ci.yml)
must pass. The matrix in [AGENTS.md § CI Quality Gates](AGENTS.md#ci-quality-gates) is the source of truth.

For CLI-visible behavior (`anthropic-news-mcp` stdio, `anthropic-news-audit`), run the
binary and confirm output — type checks and tests alone don't verify CLI behavior.

## Agent / Subagent Usage

- Use the `Explore` agent for "where is X" / "which files reference Y" only.
- Use [.claude/agents/source-implementer.md](.claude/agents/source-implementer.md) for end-to-end fetcher work.
- Use [.claude/agents/quality-gate-runner.md](.claude/agents/quality-gate-runner.md) to run the full verification matrix.
- Path-scoped rules in [.claude/rules/](.claude/rules/) apply when working in matching paths.

## When Unsure

Proceed without asking if: change is local, reversible, covered by tests, and within one
layer. Ask first if: touches host allowlist, schema version, dedup ranking, auth/remote
ASGI, source-key rename, or any change that affects multiple sources at once.

## Docs Map

| Need | File |
|---|---|
| Cross-tool agent overview | [AGENTS.md](AGENTS.md) |
| Add a source (skill form) | [.claude/skills/add-source.md](.claude/skills/add-source.md) |
| Path rules (fetchers/cache/server/tests/flags) | [.claude/rules/](.claude/rules/) |
| Slash commands (verify, add-source, debug-source) | [.claude/commands/](.claude/commands/) |
| Cache reset runbook | [docs/runbooks/cache-reset.md](docs/runbooks/cache-reset.md) |
| Source failure runbook | [docs/runbooks/source-failure.md](docs/runbooks/source-failure.md) |
| Dashboards / observability | [docs/dashboards.md](docs/dashboards.md) |
| MCP schema export | [docs/schema.json](docs/schema.json) |
| Eval methodology | [evals/README.md](evals/README.md), [evals/rubric.md](evals/rubric.md) |
| Project wiki (auto-generated) | [droid-wiki/](droid-wiki/) — read-only, do not hand-edit |
