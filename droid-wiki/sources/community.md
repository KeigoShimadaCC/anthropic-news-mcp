# Community sources

Two fetchers cover community discussion. Both are source type `COMMUNITY` with evidence tier `LOW` — they're useful as secondary signal but should not be treated as primary evidence. The trust-ranked dedup ranks them below GitHub, which ranks below docs and official.

## HackerNewsFetcher (`hn-anthropic`)

| | |
|---|---|
| API | `GET https://hn.algolia.com/api/v1/search?query=anthropic+OR+%22claude+ai%22&tags=story&hitsPerPage=20` |
| Min score | 10 points |
| TTL | 30 min |
| Default categories | community |
| File | `src/anthropic_news_mcp/fetchers/hackernews.py` |

Uses HN's Algolia-backed search API. Filters out stories below 10 points. Title comes straight from the hit. URL falls back to `https://news.ycombinator.com/item?id=<objectID>` when the hit has no external URL (Show HN, Ask HN). Summary is the first 400 chars of `story_text` (HTML stripped) when present, otherwise `<points> points · <num_comments> comments on Hacker News`.

ID is `hn-<objectID>`. Author from the hit's `author` field.

Importance:
- `> 500` points → `3`
- `> 100` points → `2`
- otherwise → `1`

## RedditFetcher (`reddit-claude`)

| | |
|---|---|
| API | `GET https://www.reddit.com/r/{subreddit}/hot.json?limit=10` |
| Subreddits | `r/ClaudeAI`, `r/anthropic` |
| TTL | 60 min |
| Default categories | community |
| File | `src/anthropic_news_mcp/fetchers/reddit.py` |

Pulls the top 10 hot posts from each subreddit. Skips stickied/pinned posts. Title is HTML-decoded. Summary is `selftext` (HTML stripped, decoded) truncated to 300 chars; falls back to `<ups> upvotes · <num_comments> comments` for link posts. URL is the Reddit permalink (`https://reddit.com<permalink>`).

ID is `reddit-<post_id>`. Author is `u/<author>`.

Importance:
- `> 500` upvotes → `2`
- otherwise → `1`

### Reddit user-agent quirk

Reddit blocks the default `httpx`-style User-Agent aggressively, so this fetcher overrides the UA to `anthropic-news-mcp/1.0`. It also tolerates HTTP `403` and `429` from Reddit by skipping that subreddit silently — without this, a Reddit rate-limit would propagate as a fetch failure and mark the source `DOWN`. Skipping a subreddit on temporary failure preserves whatever items came back from the other subreddit.

## Why community sources matter

Community signals catch discussion that the official surfaces don't cover: third-party reviews, model behavior reports, ecosystem libraries, complaints, and capability demonstrations. The retrieval layer keeps them strictly below official sources in trust ranking, but they fill a real gap.

Tools that filter on `source_types` (e.g. `search_web_sources`, `get_timeline`) can include or exclude `community` cleanly. The `signals_by_source_type` block in `get_timeline`'s response always separates community signals from official signals so a digest model can keep them distinct.

## Test fixtures

Fixtures for these fetchers live in `tests/fixtures/`:

- `hackernews.json`
- `reddit_claudeai.json`, `reddit_anthropic.json`

Tests live in `tests/test_fetchers/test_community.py`.
