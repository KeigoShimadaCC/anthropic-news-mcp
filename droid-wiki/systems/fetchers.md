# Fetchers

Each source has a fetcher class that turns a remote response into a list of `NewsItem`s. Fetchers are stateless, async, and never touch the cache — they exist only to perform one HTTP request and parse the result.

## Purpose

Encapsulate every source-specific quirk (pagination, date formats, HTML structure, JSON shape) behind a single `async def fetch() -> list[NewsItem]` interface so the retrieval layer can treat all sources uniformly.

## The `Fetcher` ABC

`src/anthropic_news_mcp/fetchers/base.py`:

```python
class Fetcher(ABC):
    source_key: str  # set as a class variable on subclasses

    @abstractmethod
    async def fetch(self) -> list[NewsItem]: ...
```

Every concrete fetcher:

- Sets `source_key` as a class variable (matching the corresponding `SourceConfig.key`).
- Raises on transport-level failures. The retrieval layer catches and sanitizes.
- Returns `[]` for empty sources.
- Performs no caching of its own.
- Holds no instance state between calls.

## Module map

| Module | Sources implemented |
|--------|---------------------|
| `fetchers/newsroom.py` | `NewsroomFetcher` (anthropic.com/news) |
| `fetchers/official.py` | `StatusFetcher`, `ResearchFetcher`, `EngineeringFetcher`, `ClaudeAppsDocsFetcher`, `SystemPromptsDocsFetcher`, `SupportReleaseNotesFetcher`, `EconomicIndexFetcher`, `BusinessInfrastructureFetcher`, `TrustPolicyFetcher` |
| `fetchers/docs_api.py` | `ApiDocsFetcher` |
| `fetchers/docs_claude_code.py` | `ClaudeCodeDocsFetcher` |
| `fetchers/github_releases.py` | `GitHubReleasesFetcher` |
| `fetchers/github_events.py` | `GitHubOrgEventsFetcher` |
| `fetchers/github_issues.py` | `GitHubIssuesPullsFetcher` |
| `fetchers/hackernews.py` | `HackerNewsFetcher` |
| `fetchers/reddit.py` | `RedditFetcher` |

`official.py` is the largest module (~640 lines) because it owns shared HTML and JSON parsers used by several Anthropic listing pages.

## Shared HTTP client

All fetchers go through `get_client()` in `src/anthropic_news_mcp/http.py`:

```python
def get_client(**kwargs) -> httpx.AsyncClient:
    ...
    response_hooks.append(_validate_response_host)
    return httpx.AsyncClient(
        timeout=Timeout(15.0, connect=5.0),
        headers={"User-Agent": f"anthropic-news-mcp/{__version__} ..."},
        follow_redirects=True,
        max_redirects=5,
        event_hooks=event_hooks,
        ...
    )
```

The client:

- Sends a stable User-Agent identifying the project and version.
- Times out at 15 seconds total (5 seconds to connect).
- Follows up to 5 redirects.
- Runs `_validate_response_host` on every response to reject hosts outside `_ALLOWED_FETCH_HOSTS`. This blocks open-redirect attacks that might otherwise let a fetcher land on an arbitrary host.

The allowlist covers every host the fetchers need to reach: `api.github.com`, `anthropic.com`, `www.anthropic.com`, `claude.ai`, `docs.claude.com`, `docs.anthropic.com`, `github.com`, `hn.algolia.com`, `news.ycombinator.com`, `platform.claude.com`, `raw.githubusercontent.com`, `reddit.com`, `www.reddit.com`, `status.claude.com`, and `support.claude.com`.

## Shared parsers in `official.py`

Two parsing helpers are reused across fetchers:

`parse_anthropic_listing_html(html, *, source_key, id_prefix, page_url, default_categories, href_contains, limit, importance)` — Walks every `<a href>` in an Anthropic listing page (news, research, engineering), filters by `href_contains`, extracts a heading-style title, optional summary paragraph, and section-derived category. Used by `NewsroomFetcher`, `ResearchFetcher`, `EngineeringFetcher`, `EconomicIndexFetcher`, `BusinessInfrastructureFetcher`, and `TrustPolicyFetcher`.

`parse_release_notes_html(html, *, source_key, id_prefix, url, categories, title_prefix, limit)` — Walks `<h1..h4>` headings, treats month-only headings as a current-month context, parses date headings, and gathers any following `<ul>`/`<li>`/`<p>` content as a summary. Used by all four `docs.claude.com` and `support.claude.com` release-note fetchers.

`parse_status_payloads(...)` — Builds items from the three Statuspage JSON endpoints (`summary.json`, `incidents.json`, `scheduled-maintenances/upcoming.json`). Used by `StatusFetcher`.

`_filter_items(items, ..., terms, categories)` — Filters a previously-parsed list to those whose `title + summary + tags` match any of a set of terms. Used by `BusinessInfrastructureFetcher` (compute, partnership, funding, datacenter, etc.) and `TrustPolicyFetcher` (RSP, safeguard, red-team, alignment, etc.).

## Date parsing

Source pages use varied date formats. Two regexes in `official.py` handle the common cases:

- `_DATE_RE` — matches `Jan 5, 2026`, `January 5th 2026`, etc.
- `_MONTH_SECTION_RE` — matches `January 2026` heading-style sections used as the implicit month for nested day headings.

`_parse_date(text)` tries the inline form first, then falls back to the section form using `default_day=1`. Returns `None` if nothing matches; the caller sets `date_confidence=UNKNOWN` in that case.

## ID generation

Stable IDs are critical because items dedupe across sources by canonical URL but are joined to the cache by ID. Conventions:

- `_stable_id(prefix, value)` returns `<prefix>-<sha1(value)[:16]>`. Used when no native ID exists (Anthropic newsroom, research, engineering listings).
- `docs-cc-<version>` for Claude Code changelog versions.
- `docs-api-<slugified-date-heading>` for API release notes.
- `docs-<source>-<slug>` for other docs release notes.
- `github-release-<release_id>`, `github-event-<event_id>`, `github-issue-<repo>-<number>` for GitHub.
- `hn-<objectID>`, `reddit-<post_id>` for community sources.
- `status-rollup-<indicator>`, `status-incident-<id>`, `status-maintenance-<id>` for status.

Once an ID is chosen for an item it must be stable across fetches — otherwise the item history table fills with phantom entries.

## GitHub authentication

Three GitHub fetchers honor `GITHUB_TOKEN`:

- `GitHubReleasesFetcher`
- `GitHubOrgEventsFetcher`
- `GitHubIssuesPullsFetcher`

Without a token, the GitHub API allows 60 requests per hour. With one (no scopes needed for public repos), the limit rises to 5,000. The first two also emit a warning when the token is absent.

## Reddit user agent quirk

`RedditFetcher` overrides the User-Agent to `anthropic-news-mcp/1.0` because Reddit blocks the default `httpx`-style UA aggressively. It also tolerates 403 and 429 from the public Reddit JSON endpoints by skipping that subreddit instead of failing the whole fetch.

## Importance heuristics

Different sources translate engagement signals into `importance` differently:

| Source | Heuristic |
|--------|-----------|
| Newsroom | Constant `3` (highest) |
| Research / Engineering | `3` if policy-related, else `2` |
| Docs release notes | Constant `2` |
| GitHub releases / events | Constant `2` |
| GitHub issues | `2` for PRs, `1` for issues |
| Hacker News | `>500` points → `3`, `>100` → `2`, else `1` |
| Reddit | `>500` upvotes → `2`, else `1` |
| Status incidents | `critical`/`major` → `3`, `minor` → `2`, else `1` |

These are advisory — they feed into the dedup ranking and the `importance` filter on `search_web_sources`.

## Adding a new fetcher

The two-step recipe:

1. Create `src/anthropic_news_mcp/fetchers/<name>.py` with a class inheriting from `Fetcher`. Set `source_key` as a class variable. Implement `async def fetch(self) -> list[NewsItem]`. Use `get_client()` for HTTP.
2. Add a `SourceConfig(...)` entry to `_build_registry()` in `src/anthropic_news_mcp/config.py`. Import the new class inside that function (the import is inside the function to avoid circular imports).

For tests, freeze a real response into `tests/fixtures/<name>.<ext>` and add a unit test in `tests/test_fetchers/test_<name>.py` that calls the parser directly without HTTP.

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/fetchers/base.py` | The `Fetcher` ABC |
| `src/anthropic_news_mcp/fetchers/official.py` | Shared parsers and the seven Anthropic-domain fetchers |
| `src/anthropic_news_mcp/fetchers/newsroom.py` | The `/news` listing fetcher |
| `src/anthropic_news_mcp/fetchers/docs_api.py` | API release notes |
| `src/anthropic_news_mcp/fetchers/docs_claude_code.py` | Claude Code CHANGELOG.md |
| `src/anthropic_news_mcp/fetchers/github_releases.py` | GitHub releases (4 repos) |
| `src/anthropic_news_mcp/fetchers/github_events.py` | GitHub org events (releases + new repos) |
| `src/anthropic_news_mcp/fetchers/github_issues.py` | GitHub issue/PR search |
| `src/anthropic_news_mcp/fetchers/hackernews.py` | HN Algolia search |
| `src/anthropic_news_mcp/fetchers/reddit.py` | r/ClaudeAI + r/anthropic JSON |
| `src/anthropic_news_mcp/http.py` | Shared httpx client and host allowlist |

## Entry points for modification

- To support a new source: follow the two-step recipe above. See [Adding a new source](../how-to-contribute/development-workflow.md).
- To change importance heuristics: edit the per-fetcher `_importance(...)` helpers in `hackernews.py` and `reddit.py`, or the constants in `official.py`.
- To allow a new outbound host: add it to `_ALLOWED_FETCH_HOSTS` in `src/anthropic_news_mcp/http.py`.
- To change the User-Agent: edit `_HEADERS` in `http.py` and the override in `reddit.py`.
