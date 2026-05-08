# Official Anthropic sources

Seven sources reach into the `anthropic.com` and `status.claude.com` family of properties. They all return items at evidence tier `HIGH` and source type `OFFICIAL`. Several of them share parsing helpers in `src/anthropic_news_mcp/fetchers/official.py`.

## NewsroomFetcher (`anthropic-newsroom`)

| | |
|---|---|
| Source URL | `https://www.anthropic.com/news` |
| TTL | 30 min |
| Default categories | models, research, policy, business |
| File | `src/anthropic_news_mcp/fetchers/newsroom.py` |

Fetches the news listing page and parses each `/news/...` anchor. Title is taken from the first heading inside the anchor or, failing that, the anchor's first non-date, non-section text line. Date is parsed by the inline `_DATE_RE`. Importance is fixed at `3`.

## StatusFetcher (`anthropic-status`)

| | |
|---|---|
| Source URLs | `https://status.claude.com/api/v2/{summary,incidents,scheduled-maintenances/upcoming}.json` |
| TTL | 5 min |
| Default categories | ops |
| File | `src/anthropic_news_mcp/fetchers/official.py::StatusFetcher` |

Pulls three Statuspage endpoints and merges them. The summary endpoint produces a single rollup item when the indicator is non-`none`. Each incident and scheduled maintenance becomes its own item. `parse_status_payloads` and `_status_item` build the items, mapping impact (`critical`, `major`, `minor`) to importance and applying validated tag sets (`_VALID_IMPACT_TAGS`, `_VALID_STATUS_TAGS`) so downstream filtering is safe.

## ResearchFetcher (`anthropic-research`)

| | |
|---|---|
| Source URL | `https://www.anthropic.com/research` |
| TTL | 60 min |
| Default categories | research |
| File | `src/anthropic_news_mcp/fetchers/official.py::ResearchFetcher` |

Calls `parse_anthropic_listing_html` filtering anchors by `href_contains="/research/"`.

## EngineeringFetcher (`anthropic-engineering`)

| | |
|---|---|
| Source URL | `https://www.anthropic.com/engineering` |
| TTL | 60 min |
| Default categories | engineering |
| File | `src/anthropic_news_mcp/fetchers/official.py::EngineeringFetcher` |

Same shape as `ResearchFetcher` but with `href_contains="/engineering/"`.

## EconomicIndexFetcher (`anthropic-economic-index`)

| | |
|---|---|
| Source URLs | `https://www.anthropic.com/economic-index` and `https://www.anthropic.com/research` |
| TTL | 120 min |
| Default categories | economics, research |
| File | `src/anthropic_news_mcp/fetchers/official.py::EconomicIndexFetcher` |

Fetches both the Economic Index landing page and the research listing, then keeps any research item whose category contains `ECONOMICS` or whose `title + summary` mentions "economic". This is the cross-cutting source: items that appear here also appear in the research source under their original keys.

## BusinessInfrastructureFetcher (`anthropic-business-infrastructure`)

| | |
|---|---|
| Source URL | `https://www.anthropic.com/news` |
| TTL | 60 min |
| Default categories | business |
| File | `src/anthropic_news_mcp/fetchers/official.py::BusinessInfrastructureFetcher` |

Re-parses the newsroom listing, then filters via `_filter_items(..., terms=_BUSINESS_TERMS, ...)` — keeps items whose `title + summary + tags` contain any of: compute, infrastructure, partnership, partner, funding, investment, investor, enterprise, customer, revenue, demand, cloud, amazon, aws, google cloud, microsoft, datacenter, data center.

Filtered items get a re-derived stable ID (prefix `business-infra`) and have category `BUSINESS` prepended. This is intentional duplication: the same announcement appears under both the newsroom key and this business-focused key, with the newsroom representative winning trust-ranked dedup. The business key exists for clients that want to query exclusively for business signals via the `sources` filter.

## TrustPolicyFetcher (`anthropic-trust-policy`)

| | |
|---|---|
| Source URLs | `https://www.anthropic.com/news`, `https://www.anthropic.com/research` |
| TTL | 60 min |
| Default categories | policy |
| File | `src/anthropic_news_mcp/fetchers/official.py::TrustPolicyFetcher` |

Same pattern as the business fetcher but filters with `_TRUST_TERMS`: responsible scaling, RSP, safety, policy, trust, transparency, red team, red-team, compliance, safeguard, preparedness, alignment, security, misuse. Items get the `policy` category and a `trust-policy` ID prefix.

## Shared parsing helpers

These fetchers all live in `src/anthropic_news_mcp/fetchers/official.py` and share the helpers documented in [Fetchers](../systems/fetchers.md):

- `parse_anthropic_listing_html(...)` — generic Anthropic listing parser
- `parse_status_payloads(...)` — Statuspage JSON merger
- `_filter_items(...)` — keyword filter for the business and trust filtered sources
- `_DATE_RE`, `_MONTH_SECTION_RE`, `_parse_date(...)` — date parsing
- `_categories_from_text(...)` — section-to-category mapping
- `_stable_id(prefix, value)` — SHA-1 truncated stable IDs

## Test fixtures

Fixtures for these fetchers live in `tests/fixtures/`:

- `newsroom.html`, `newsroom_filters.html` — tests cover the standard listing and the business/trust filtered variants
- `research.html`, `engineering.html`
- `status_operational.json`, `status_incidents.json`, `status_scheduled.json`

See `tests/test_fetchers/test_newsroom.py` and `tests/test_fetchers/test_official.py`.
