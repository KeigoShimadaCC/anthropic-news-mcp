# Eval Suite

This directory contains a 20-prompt evaluation harness that scores the
`anthropic-news-mcp` server using `claude-haiku-4-5` as judge.

## What it measures

Each prompt is scored on three dimensions (0–2 each), for a maximum of 6 per prompt:

| Dimension | What it checks |
|-----------|---------------|
| **Tool selection** | Did Claude call the right tool with the right params? |
| **Faithfulness** | Are all claims grounded in tool output (no hallucination)? |
| **Helpfulness** | Is the response clear and useful to the user? |

**Pass threshold: mean ≥ 5.0 / 6.0 across 20 prompts.**

See [rubric.md](./rubric.md) for the full scoring guide.

## Running the eval

```bash
# Install eval dependencies
pip install -e ".[eval]"

# Set required env vars
export ANTHROPIC_API_KEY=sk-ant-...

# Run (takes ~2 minutes, costs ~$0.15)
python evals/run_eval.py

# Results are written to evals/results/<timestamp>.json
```

## Files

| File | Purpose |
|------|---------|
| `golden.yaml` | 20 Q&A pairs with expected tools and response criteria |
| `rubric.md` | Scoring rubric for the LLM judge |
| `run_eval.py` | Harness: drives the MCP server, calls Haiku as judge |
| `results/` | Output JSON files (gitignored except `.gitkeep`) |

## How the harness works

1. Spawns the MCP server as a subprocess (realistic — matches production behavior)
2. Creates an Anthropic SDK client that can call MCP tools
3. For each of the 20 golden prompts:
   a. Sends the prompt to `claude-haiku-4-5` with MCP tools available
   b. Records which tools were called and with what arguments
   c. Captures the final text response
   d. Calls a *second* Haiku instance (the judge) with the rubric + expected output
   e. Parses the 0/1/2 score per dimension
4. Aggregates scores and writes a Markdown + JSON summary

## Cost estimate

20 prompts × ~2 LLM calls × ~2K tokens each ≈ 80K tokens ≈ **$0.10–0.20 per run**

The GitHub Actions eval workflow (`eval.yml`) is manually triggered only, so costs
are never incurred automatically.
