# GitHub sources

Three fetchers cover the GitHub side of Anthropic's footprint. All three set source type `GITHUB` with evidence tier `MEDIUM`. They all honor `GITHUB_TOKEN` to raise the API rate limit from 60 to 5,000 requests per hour.

## GitHubReleasesFetcher (`anthropic-github-releases`)

| | |
|---|---|
| API | `GET https://api.github.com/repos/{repo}/releases?per_page=5` for each repo |
| Repos | `anthropics/claude-code`, `anthropics/anthropic-sdk-python`, `anthropics/anthropic-sdk-typescript`, `modelcontextprotocol/modelcontextprotocol` |
| TTL | 30 min |
| Default categories | claude-code, models |
| File | `src/anthropic_news_mcp/fetchers/github_releases.py` |

For each repo, fetches the most recent five releases. Skips drafts. Title is `<repo> <tag>: <name>` or `<repo> <tag>` if name and tag are equal. Body is HTML-stripped and truncated to 400 chars. ID is `github-release-<release_id>`. Importance fixed at `2`.

Categories per repo: `[claude-code]` for claude-code and MCP repos, `[models, claude-code]` for SDK repos, otherwise `[claude-code]`.

When the token is unset, emits a `warnings.warn(...)` once per fetch reminding operators to set `GITHUB_TOKEN`.

## GitHubOrgEventsFetcher (`anthropic-github-events`)

| | |
|---|---|
| API | `GET https://api.github.com/orgs/anthropics/events?per_page=50` |
| TTL | 30 min |
| Default categories | claude-code |
| File | `src/anthropic_news_mcp/fetchers/github_events.py` |

Walks the org-wide event stream and keeps two event types:

- `ReleaseEvent` with `action == "published"` — produces an item titled `<repo> <tag>` linking to the release page. Deduped per `(repo, tag)`.
- `CreateEvent` with `ref_type == "repository"` — produces an item titled `New repo created: <repo>` linking to the repo. Deduped per repo.

ID is `github-event-<event_id>`. Importance fixed at `2`.

When the token is unset, emits a structured `_log.warning(...)`.

## GitHubIssuesPullsFetcher (`anthropic-github-issues-prs`)

| | |
|---|---|
| API | `GET https://api.github.com/search/issues?q={escaped_query}&per_page=20` |
| Repos | Same four repos as GitHubReleasesFetcher |
| Query | `repo:... repo:... ... updated:>=2025-01-01 sort:updated-desc` |
| TTL | 30 min |
| Default categories | claude-code, engineering |
| File | `src/anthropic_news_mcp/fetchers/github_issues.py` |

Uses GitHub's issue-search API with a constructed query that scopes to the four repos and filters to issues updated since 2025-01-01. The `pull_request` field on a hit distinguishes PRs from issues.

Title is `<repo> {PR|issue} #<number>: <title>`. Tags include `github`, `pull-request` or `issue`, and the first eight label names. Importance is `2` for PRs, `1` for issues.

ID is `github-issue-<repo-with-slashes-replaced>-<number>`.

## Why the same repos appear in three sources

Each fetcher exposes a different facet of GitHub activity:

- `github-releases` — formal releases with full release notes (stable, dated, cite-worthy).
- `github-events` — raw event stream including new repos.
- `github-issues-prs` — recent issue and PR activity, useful for tracking discussion and active work.

When a release lands in all three (release page, ReleaseEvent, related PRs), trust-ranked dedup picks one representative based on registry order — `github-releases` is registered first, so its richer body wins.

## Test fixtures

Fixtures for these fetchers live in `tests/fixtures/`:

- `github_releases.json` — full GitHub Releases API response shape
- `github_events.json` — real-world `org/events` payload
- `github_events_synthetic.json` — synthetic minimal payload for edge cases

Tests live in `tests/test_fetchers/test_github.py`.
