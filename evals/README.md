# Eval Suite

This directory contains a golden-prompt evaluation harness that scores the
`anthropic-news-mcp` server using `claude-haiku-4-5` as judge.

## What it measures

Each prompt is scored on three dimensions (0–2 each), for a maximum of 6 per prompt:

| Dimension | What it checks |
|-----------|---------------|
| **Tool selection** | Did Claude call the right tool with the right params? |
| **Faithfulness** | Are all claims grounded in tool output (no hallucination)? |
| **Helpfulness** | Is the response clear and useful to the user? |

**Pass threshold: mean ≥ 5.0 / 6.0 across all prompts.**

See [rubric.md](./rubric.md) for the full scoring guide.

## Running the eval

```bash
# Install eval dependencies
pip install -e ".[eval]"

# Set required env vars
export ANTHROPIC_API_KEY=sk-ant-...

# Run live eval (takes ~2 minutes, costs ~$0.15)
python evals/run_eval.py

# Run with deterministic seeded cache snapshots before prompting
python evals/run_eval.py --seed-cache

# Results are written to evals/results/<timestamp>.json
```

`--seed-cache` does not remove the need for `ANTHROPIC_API_KEY`; it keeps source data
deterministic while the model and judge calls still run through the Anthropic API.

## Live Source Audit

Source health checks are separate from evals and are opt-in because they perform live HTTP
requests:

```bash
anthropic-news-audit
anthropic-news-audit --sources anthropic-status,anthropic-engineering
anthropic-news-audit --json evals/results/source_audit_$(date -u +%Y%m%dT%H%M%SZ).json
anthropic-news-audit --strict
```

The audit reports fetch status, item counts, newest published date, elapsed milliseconds,
sample titles, sanitized errors, and warnings for empty or stale canonical sources.

## Files

| File | Purpose |
|------|---------|
| `golden.yaml` | Golden prompts with expected tools, parameters, and response criteria |
| `rubric.md` | Scoring rubric for the LLM judge |
| `run_eval.py` | Harness: drives the MCP server, calls Haiku as judge |
| `results/` | Output JSON files (gitignored except `.gitkeep`) |

## How the harness works

1. Optionally seeds the SQLite cache with deterministic snapshots
2. Creates an Anthropic SDK client that can call MCP tools
3. For each golden prompt:
   a. Sends the prompt to `claude-haiku-4-5` with MCP tools available
   b. Records which tools were called and with what arguments
   c. Captures the final text response
   d. Calls a *second* Haiku instance (the judge) with the rubric + expected output
   e. Parses the 0/1/2 score per dimension
4. Aggregates scores and writes a JSON summary

## Cost estimate

27 prompts × ~2 LLM calls × ~2K tokens each ≈ 108K tokens ≈ **$0.10–0.25 per run**

The GitHub Actions eval workflow (`eval.yml`) is manually triggered only, so costs
are never incurred automatically.
