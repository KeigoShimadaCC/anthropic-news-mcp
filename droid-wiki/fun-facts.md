# Fun facts

A few things worth pointing out about this codebase.

## The whole project is younger than most pull requests

Every line was committed within a 19-hour window on May 7–8, 2026. The first commit (`58898d2 chore: project scaffold`) and the latest commit (`7f769e1 Enhance documentation and logging features`) are 19 hours and 4 minutes apart. 27 commits, five distinct eras, one author. See [Lore](./lore.md) for the timeline.

## The largest commit is mostly fixtures

Commit `a88c8ec feat: fetcher base + newsroom + docs (CC + API)` is 7,511 insertions across 13 files. Looking at the actual code: most of those lines are HTML and JSON test fixtures. `tests/fixtures/docs_api.html` alone is 990 KB and 2,023 lines. `tests/fixtures/docs_claude_code.html` is 768 KB. Frozen, real-world HTML is bulky.

## Reddit blocks default User-Agents

`src/anthropic_news_mcp/fetchers/reddit.py` overrides the User-Agent to `anthropic-news-mcp/1.0` because the public Reddit JSON endpoints aggressively reject default-looking UAs:

```python
headers = {"User-Agent": "anthropic-news-mcp/1.0"}
```

The fetcher also tolerates HTTP 403 and 429 from Reddit silently, treating them as "this subreddit is unavailable right now" rather than as fetch failures.

## AI co-authorship is in the git trailers

A grep for `Co-authored-by` in commit messages turns up frequent `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` trailers. The project was built mostly through AI-assisted development, with the human author driving review and design choices. The dedicated `CLAUDE.md` file at the repo root exists specifically to give Claude Code the architectural context it needs to navigate the codebase quickly.

## The cache schema is intentionally disposable

`CACHE_SCHEMA_VERSION` lives in `src/anthropic_news_mcp/cache.py`. There's no migration framework — when you bump the version, `init_db()` recreates the schema from scratch on next run. Losing the cache just forces a refetch on next call, so this is fine. It also means schema changes can be aggressive without backward compatibility ceremony.

## Source dedup ranks summary length

The `_representative_key` tuple in `src/anthropic_news_mcp/retrieval.py` includes `min(len(item.summary.strip()), 400)` as a tie-breaker. When two items share a canonical URL and rank equally on source type, evidence tier, presence of `published_at`, and importance, the one with the longer summary wins (capped at 400 chars). Higher-effort summaries win. The cap stops a 5,000-char dump from automatically winning over a thoughtful 350-char one.

## The remote server refuses to start without env vars

`src/anthropic_news_mcp/remote.py::RemoteAuthConfig.from_env` raises:

> `RuntimeError: Refusing insecure remote MCP startup; missing required environment: ANTHROPIC_NEWS_MCP_AUTH_ISSUER, ...`

There is no debug mode that lets you bypass auth. The trade-off: someone who copies a `uvicorn anthropic_news_mcp.asgi:app` example without reading the docs can't accidentally expose the surface unauthenticated.

## Audit knows which sources are "canonical"

`src/anthropic_news_mcp/audit.py` has an explicit set of nine sources marked `_CANONICAL_REQUIRED`:

```python
_CANONICAL_REQUIRED = {
    "anthropic-newsroom", "anthropic-status", "anthropic-research",
    "anthropic-engineering", "anthropic-docs-api", "anthropic-docs-claude-apps",
    "anthropic-docs-system-prompts", "anthropic-support-release-notes",
    "anthropic-economic-index",
}
```

These are sources that should never legitimately be empty. With `--strict`, the audit exits 1 if any of them fail or warn. It's a tiny gate that catches the real "Anthropic broke a page" scenarios.

## The eval suite costs ~$0.15 per run

The README puts a hard number on the LLM judge harness: 27 prompts × ~2 LLM calls × ~2K tokens per call ≈ 108K tokens, which prices out to ~$0.10–0.25 per run with `claude-haiku-4-5`. The GitHub Actions workflow `eval.yml` is `workflow_dispatch` only — manual trigger — specifically so unattended pushes never spend money.

## "anthropic-news" is just v1 scope

From the README:

> The architecture is source-agnostic. Adding, say, an OpenAI changelog source is:
> 1. Create `src/anthropic_news_mcp/fetchers/openai_changelog.py` implementing `Fetcher`
> 2. Add a `SourceConfig` entry to `SOURCE_REGISTRY` in `config.py`
>
> The `anthropic-news-mcp` name reflects v1 scope, not an architectural constraint.

Nothing in the code is Anthropic-specific. The package name and category enum lean Anthropic-shaped, but the fetcher framework is generic.

## Two HN stories are needed to count

`src/anthropic_news_mcp/fetchers/hackernews.py` filters HN hits to ≥10 points:

```python
_MIN_POINTS = 10
```

Anything below that is treated as noise. The threshold is low enough to catch early signal but high enough to filter out single-comment posts.

## The changelog is the git log

There's no `CHANGELOG.md` at the repo root. The 27-commit `git log` is the changelog. Commit messages use clear category prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`) so a `git log --oneline` reads as a chronological release-note feed.
