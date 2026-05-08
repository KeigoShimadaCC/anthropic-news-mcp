# Primitives

The `models.py` module defines the canonical data types every other module passes around. Everything in the project is some flavor of these types.

| Type | Purpose | Page |
|------|---------|------|
| `NewsItem` | A single news, changelog, release, or community item | [News item](./news-item.md) |
| `SourceConfig` | Registry entry for one source | [Source config and registry](./source-config.md) |
| `ContentDetail`, `EvidenceExcerpt`, `DedupCluster`, `TimelineGroup` | Evidence-first research types | [Evidence](./evidence.md) |
| `SourceHealth` | Operational state per source | [Source config and registry](./source-config.md) |
| `ResearchSession`, `ResearchNote`, `ResearchReport` | Research session state | [Evidence](./evidence.md) |
| `ClaimEvaluationResult` | Output of `evaluate_claims` | [Evidence](./evidence.md) |
| Enums: `Category`, `Source`, `SourceType`, `EvidenceTier`, `SourceStatus`, `DateConfidence`, `ClaimSupport` | Closed value sets | [News item](./news-item.md) |

Every type is a `pydantic.BaseModel` (or a `StrEnum` for the closed enums). All datetime fields are timezone-aware UTC.

## Module layout

| File | Contents |
|------|----------|
| `src/anthropic_news_mcp/models.py` | All Pydantic models and enums |
| `src/anthropic_news_mcp/config.py` | `SourceConfig` dataclass and `SOURCE_REGISTRY` |

## Why these types matter

The models double as the wire format for MCP tool responses. `model_dump(mode="json")` serializes a `NewsItem` straight into the JSON payload returned to the client. Adding a field to a model adds it to every tool response that includes that model — there's no separate schema layer. Treat changes to these types as breaking changes for clients.
