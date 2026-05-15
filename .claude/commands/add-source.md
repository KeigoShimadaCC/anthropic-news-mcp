# /add-source

Add a new Anthropic-related news source.

## Input expected
- Source key (format: `anthropic-<name>`).
- Source URL (host must be allowlisted in `http._ALLOWED_FETCH_HOSTS`).
- Source type: `OFFICIAL` | `DOCS` | `GITHUB` | `COMMUNITY`.
- Default categories from `Category` enum in `models.py`.
- TTL in seconds (e.g. 1800 for newsroom-class, 300 for status-class).

## Steps
1. Read [.claude/skills/add-source.md](../skills/add-source.md) for the procedure.
2. Delegate to the `source-implementer` agent with the inputs above.
3. Surface the agent's verification checklist results.

## Stop condition
Fetcher + fixture + test + registry entry exist, all listed checks green.

## Output
- Files added (paths).
- `SourceConfig` summary line.
- Verification table from the agent.
