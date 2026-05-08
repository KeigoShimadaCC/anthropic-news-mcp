# Eval Rubric

Each of the 27 golden prompts is scored on three dimensions, each 0–2:

## Dimensions

### 1. Tool selection (0–2)

| Score | Meaning |
|-------|---------|
| 0 | Wrong tool called, or Claude hallucinated an answer without calling any tool |
| 1 | Right tool family but missing key parameters (e.g., no `since` on a time-bounded query) |
| 2 | Correct tool with appropriate parameters matching the query intent |

### 2. Faithfulness (0–2)

| Score | Meaning |
|-------|---------|
| 0 | Response contains hallucinated content not present in the tool output |
| 1 | Mostly grounded, minor drift (paraphrasing that changes meaning) |
| 2 | All factual claims trace directly to tool output; honest about limitations |

### 3. Helpfulness (0–2)

| Score | Meaning |
|-------|---------|
| 0 | Response is useless or misleading to the user |
| 1 | Adequate — answers the question but in a flat or incomplete way |
| 2 | Clear, well-formatted, directly addresses the user's intent; graceful on failure cases |

## Scoring per response

**Total = tool_selection + faithfulness + helpfulness (max 6)**

## Suite pass threshold

**Mean score across 27 golden prompts ≥ 5.0 / 6.0**

This equates to roughly "right tool + grounded + helpful" on nearly every prompt.

## Special cases

- **Graceful failure prompts (q18–q20):** For these, `tool_selection = 2` if Claude correctly
  identifies that the request can't be satisfied and communicates why, even without calling a tool.
  `tool_selection = 0` if it halluccinates an answer.

- **`list_sources` prompt (q08):** `tool_selection = 2` only if `list_sources` is the first
  (or only) tool called — not if Claude tries `get_recent_updates` first and falls back.
