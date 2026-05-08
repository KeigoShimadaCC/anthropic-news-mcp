# How to contribute

The repo is small, single-package, and follows tight CI gates. Most contributions fall into one of three shapes: adding a new source, extending the MCP tool surface, or fixing a parser when an Anthropic page changes layout.

## Sub-pages

- [Development workflow](./development-workflow.md) — branch, code, test, PR, merge cycle, plus the new-source recipe
- [Testing](./testing.md) — pytest layout, fixtures, in-process MCP calls, mocking conventions
- [Debugging](./debugging.md) — logs, common failure modes, runbook for stale sources
- [Patterns and conventions](./patterns-and-conventions.md) — fetcher contract, registry, async patterns, error sanitization
- [Tooling](./tooling.md) — ruff, mypy, pre-commit, CI workflows, eval harness

## What good looks like

- All offline tests pass: `.venv/bin/pytest -q`
- Lint clean: `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .`
- Type clean: `.venv/bin/mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py`
- Offline eval still passes: `.venv/bin/python evals/run_offline_eval.py`
- Smoke import works: `python -c "from anthropic_news_mcp.server import mcp; print('ok')"`

CI runs all of these on every PR. The pre-commit hooks run lint, format, and mypy on every commit; pre-push runs the offline pytest suite.

## Definition of done

A change is done when:

1. The CI pipeline is green (lint, format, mypy, pytest, offline eval, security CodeQL).
2. New behavior has at least one test that exercises the offline path.
3. New external sources have a frozen fixture in `tests/fixtures/` and a parser test in `tests/test_fetchers/`.
4. New environment variables are documented in `README.md` and `.env.example`.
5. New tools, resources, or prompts have docstrings that describe arguments and the structured response shape.

## Project conventions to know

- Never call live HTTP from a test. Always parse a frozen fixture.
- Never invent a new error envelope shape. Use `_error(message, **details)` in `server.py`.
- Never swallow exceptions in fetchers. The retrieval layer catches them and produces sanitized health rows.
- Never write to the cache outside `cache.py`'s public functions.
- Never bypass `get_client()` for outbound HTTP. The host allowlist must apply uniformly.

See [Patterns and conventions](./patterns-and-conventions.md) for the full list with examples.

## CODEOWNERS

`.github/CODEOWNERS` declares `@KeigoShimadaCC` as the owner of every path. Any PR will request review from that handle automatically.
