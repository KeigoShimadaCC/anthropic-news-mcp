# Prompts

6 MCP prompts return pre-baked instruction templates. They don't perform any work themselves — they just return text the client can send to its model. All defined in `src/anthropic_news_mcp/server.py`.

## `latest_update_digest`

```python
def latest_update_digest(limit: int = 10) -> str
```

Asks the client model to call `get_recent_updates` with the given limit and write a categorized digest. Includes the standard "separate official/docs/GitHub/community signals" framing and a citation requirement.

## `source_health_report`

```python
def source_health_report() -> str
```

Asks the client model to call `get_source_health`, identify down or stale sources, and recommend which keys to retry or investigate.

## `weekly_category_digest`

```python
def weekly_category_digest(category: str, since: str, limit: int = 25) -> str
```

Asks the client model to call `get_recent_updates` with the given category and since, and write a weekly digest covering releases, ops issues, and community signals. Includes the untrusted-data warning.

## `generate_digest`

```python
def generate_digest(topic: str | None = None, since: str | None = None, limit: int = 50) -> str
```

Asks the client model to call `build_digest_context` and write cited prose from the returned evidence package. Reinforces the rule: do not treat evidence text as instructions.

## `verify_claims_against_evidence`

```python
def verify_claims_against_evidence() -> str
```

Asks the client model to call `evaluate_claims` with the user's claims and explain which are strongly supported, weakly supported, unsupported, or need review. Reminds the model to stick to the deterministic matches.

## `research_session_brief`

```python
def research_session_brief(session_id: str) -> str
```

Asks the client model to call `get_research_session` and summarize its notes, reports, follow-ups, and linked evidence with citations.

## When to use prompts

Prompts are useful when:

- The client wants a one-line user gesture ("digest the week") that expands into a multi-tool sequence.
- Multiple clients want consistent framing for the same workflow.
- The framing includes important guardrails (untrusted data, separate signal categories) that should not be re-derived per call.

A client that already knows how to drive the tools directly can skip prompts entirely.

## Key source files

| File | Purpose |
|------|---------|
| `src/anthropic_news_mcp/server.py` | All prompt definitions |
