# /verify

Run the local equivalent of CI and report per-gate status. Do not edit code.

## Steps
1. Delegate to the `quality-gate-runner` agent.
2. Surface the per-gate table.
3. If any gate fails, name the first failure and stop.

## Stop condition
First non-recoverable failure, or all gates green.

## Output
- Table from the agent.
- One-line conclusion: "All gates green" or "First failure: <gate>".
