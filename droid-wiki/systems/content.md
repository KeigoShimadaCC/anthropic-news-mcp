# Content extraction

`src/anthropic_news_mcp/content.py` is the small subsystem responsible for turning a remote page into a normalized text blob plus stable evidence excerpts.

## Purpose

Given a `NewsItem` with a URL, fetch the page, strip boilerplate, normalize whitespace, hash the result, and produce 1–3 evidence excerpts that the research and digest tools can store and cite.

## Public surface

| Function | Purpose |
|----------|---------|
| `fetch_content_detail(item)` | Fetch the page, normalize text, return a `ContentDetail` |
| `build_excerpts(item, detail, *, source_type, evidence_tier, query, max_excerpts)` | Produce up to `max_excerpts` `EvidenceExcerpt`s, prioritizing query-term matches |
| `extract_text(body, content_type)` | Lower-level: turn HTML / JSON / plain text into normalized text |
| `normalize_text(text)` | Whitespace collapse |
| `content_hash(text)` | SHA-256 of UTF-8 encoded text |

## How `fetch_content_detail` works

1. Open a shared `httpx` client via `http.get_client()` (host allowlist applies).
2. `GET` the URL. Raise on HTTP errors.
3. Inspect `Content-Type`:
   - If `> 5 MB`: emit a warning, fall back to `title\n\nsummary` text.
   - If not text/JSON: emit a warning, fall back to `title\n\nsummary` text.
   - Else: extract via `extract_text(body, content_type)`.
4. Truncate to `_MAX_STORED_CHARS = 50_000` and emit a warning if truncated.
5. If extraction produced empty text, fall back to the title+summary text and warn.
6. Return a `ContentDetail` with the normalized text, content hash, content type, retrieved-at timestamp, truncation flag, and warnings list.

## HTML normalization

`extract_text` for HTML:

- Parses with `selectolax.HTMLParser`.
- Drops all `script`, `style`, `nav`, `footer`, `header`, `noscript`, `svg`, `form` elements (the `_BOILERPLATE_TAGS` constant).
- Emits the remaining text via `body.text(separator=" ", strip=True)`, falling back to the full tree if `<body>` is absent.
- Collapses runs of whitespace via `normalize_text`.

## JSON normalization

For JSON content types, `_json_text` recursively concatenates every string leaf in the parsed structure with single spaces. Non-string scalars are stringified. Whitespace is then collapsed. This produces searchable text for API responses without preserving structure.

If the body fails to parse as JSON, the text falls through to the plain-text branch.

## Excerpt windowing

`build_excerpts(item, detail, *, source_type, evidence_tier, query, max_excerpts=3)`:

1. Tokenize `query` into lowercase words of length ≥3 via `_terms`.
2. For each term, find the first occurrence in the lowercased text. Build a 900-character window centered on the match, snapping to word boundaries via `_window_for_match`.
3. Stop after `max_excerpts` distinct windows.
4. If no terms matched (or no query was given) and the text is non-empty, default to a single window over the leading 900 characters.
5. For each window, build an `EvidenceExcerpt`:
   - `evidence_id = sha256(item.id + ":" + content_hash + ":" + start + ":" + end)`
   - `start_char` and `end_char` recorded so a later refresh can verify position.
   - `source_type` and `evidence_tier` carried in from the registry lookup at the call site.

The `evidence_id` is content-addressed — re-running the same windowing on the same text produces the same IDs, which is what makes excerpts safely citable across calls.

## Why these limits

| Constant | Value | Rationale |
|----------|-------|-----------|
| `_MAX_STORED_CHARS` | 50,000 | Caps SQLite row size for `content_details.normalized_text`; long enough for nearly every Anthropic article |
| `_MAX_RESPONSE_BYTES` | 5,000,000 | Hard cap before extraction; large binary uploads or attacker-controlled responses fall back to title/summary |
| Window size | 900 chars | Comfortable evidence excerpt size — long enough to provide context, short enough that ~3 excerpts fit in a tool response |
| `max_excerpts` | 3 | One per priority query term |

## Integration points

- **Reads:** Remote page bodies via `http.get_client()`.
- **Writes:** Nothing directly. Callers in `research.py` and `server.py` persist via `cache.save_content_detail` and `cache.save_evidence_excerpts`.
- **Called by:** `research.get_update_detail`, `research.search_web_sources` (when `refresh=True`), `research.evaluate_claims` (the `query` fallback path).

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/content.py` | The whole content subsystem (~163 lines) |
| `src/anthropic_news_mcp/http.py` | The shared `httpx` client and host allowlist |
| `tests/test_content.py` | Unit tests for normalization and excerpt windowing |

## Entry points for modification

- To support new content types: extend the type checks in `fetch_content_detail` and add a parser to `extract_text`.
- To change excerpt size or count: edit `_window_for_match` (size) or pass a different `max_excerpts` from the research layer.
- To support markdown extraction with structure preserved: replace `extract_text`'s HTML branch with a markdown-rendering pipeline. Note that downstream code only assumes the result is whitespace-normalized text.
