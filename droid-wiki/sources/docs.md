# Docs and release notes

Five sources cover Anthropic's documentation and release-note pages. All five are source type `DOCS` with evidence tier `HIGH`. Four of them parse the same `docs.claude.com` / `support.claude.com` HTML format via `parse_release_notes_html` in `src/anthropic_news_mcp/fetchers/official.py`. One is special-cased to scrape the `claude-code` CHANGELOG.md from GitHub.

## ClaudeCodeDocsFetcher (`anthropic-docs-claude-code`)

| | |
|---|---|
| Source URL (text) | `https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md` |
| Canonical URL | `https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md` |
| Cross-reference | `https://api.github.com/repos/anthropics/claude-code/releases?per_page=100` |
| TTL | 60 min |
| Default categories | claude-code |
| File | `src/anthropic_news_mcp/fetchers/docs_claude_code.py` |

Parses the markdown CHANGELOG split by `## <version>` headings. Bullet lines following each heading become the item summary. The CHANGELOG has no inline dates, so the fetcher also calls the GitHub Releases API to look up the published date for each tag and join it back. Item IDs are `docs-cc-<version-with-dots-replaced>`.

If the GitHub releases API call fails (rate limit, network error), items are still emitted but their `published_at` is `None` and `date_confidence` is `UNKNOWN`.

## ApiDocsFetcher (`anthropic-docs-api`)

| | |
|---|---|
| Source URL | `https://platform.claude.com/docs/en/release-notes/overview` |
| TTL | 60 min |
| Default categories | models |
| File | `src/anthropic_news_mcp/fetchers/docs_api.py` |

Walks every `<h3>` matching the date regex (`Jan 5, 2026` or `January 5, 2026`), gathers the immediately following `<ul>` bullets as the summary, slugifies the heading into the ID. Item IDs are `docs-api-<slug>`.

## ClaudeAppsDocsFetcher (`anthropic-docs-claude-apps`)

| | |
|---|---|
| Source URL | `https://docs.claude.com/en/release-notes/claude-apps` |
| TTL | 60 min |
| Default categories | models |
| File | `src/anthropic_news_mcp/fetchers/official.py::ClaudeAppsDocsFetcher` |

Calls the shared `parse_release_notes_html(...)` with `id_prefix="docs-claude-apps"` and `title_prefix="Claude Apps Release Notes"`.

## SystemPromptsDocsFetcher (`anthropic-docs-system-prompts`)

| | |
|---|---|
| Source URL | `https://docs.claude.com/en/release-notes/system-prompts` |
| TTL | 60 min |
| Default categories | policy |
| File | `src/anthropic_news_mcp/fetchers/official.py::SystemPromptsDocsFetcher` |

Same parser, `id_prefix="docs-system-prompts"`, category overridden to `policy`.

## SupportReleaseNotesFetcher (`anthropic-support-release-notes`)

| | |
|---|---|
| Source URL | `https://support.claude.com/en/articles/12138966-release-notes` |
| TTL | 60 min |
| Default categories | models |
| File | `src/anthropic_news_mcp/fetchers/official.py::SupportReleaseNotesFetcher` |

Same parser, `id_prefix="support-release-notes"`, category `models`.

## Shared release-notes parser

`parse_release_notes_html(...)` in `src/anthropic_news_mcp/fetchers/official.py`:

1. Walks every `<h1..h4>` heading.
2. If the heading matches `_MONTH_SECTION_RE` (e.g. "January 2026"), it becomes the active month context.
3. Otherwise, the parser tries to read a date out of the heading directly. If the heading lacks a year but the active month context is set, it splices day + month + year together.
4. Once a date is parsed, it walks forward through siblings until the next heading at the same or higher level, gathering `<ul>`/`<li>`/`<p>` content into a `bullets` list. The summary is `bullets[:3]` joined with ` · `.
5. Stable ID is `<id_prefix>-<slugified-date-text>`.

This handles the "January 2026" / "5th: bullet bullet bullet" / "12th: bullet bullet" / "February 2026" pattern that all four release-note pages use.

## Test fixtures

Fixtures for these fetchers live in `tests/fixtures/`:

- `docs_api.html`
- `docs_claude_code.html`, `docs_claude_code_raw.md`
- `docs_claude_apps.html`
- `docs_system_prompts.html`
- `support_release_notes.html`

Tests live in `tests/test_fetchers/test_docs.py` and `tests/test_fetchers/test_official.py`.
