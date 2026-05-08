# Runbook: Sentry Error Tracking Setup

## Overview

The server supports optional Sentry error tracking. When `SENTRY_DSN` is set, uncaught
exceptions are automatically forwarded to Sentry. No code changes are required.

## Setup

### 1. Create a Sentry project

1. Go to [sentry.io](https://sentry.io) and create a free account
2. Create a new project → select **Python**
3. Copy the **DSN** from Project Settings → Client Keys

### 2. Set the DSN

**Local development:**
```bash
export SENTRY_DSN="https://<key>@o<org>.ingest.sentry.io/<project>"
.venv/bin/anthropic-news-mcp
```

**GitHub Actions (for CI/CD):**
```
Settings → Secrets and Variables → Actions → New repository secret
Name: SENTRY_DSN
Value: <your DSN>
```

**devcontainer:**
Add to `.devcontainer/devcontainer.json`:
```json
"containerEnv": {
  "SENTRY_DSN": "${localEnv:SENTRY_DSN}"
}
```

### 3. Install the optional dependency

```bash
pip install "anthropic-news-mcp[observability]"
# or
uv pip install -e ".[observability]"
```

The `sentry-sdk` package is only required when `SENTRY_DSN` is set. Without it,
the server logs a debug message and continues normally.

## Sentry–GitHub Integration (error-to-insight pipeline)

Link Sentry issues to GitHub:

1. In Sentry: **Settings → Integrations → GitHub** → Connect
2. In repository settings: **Code Mappings** → map `src/anthropic_news_mcp` → `src/anthropic_news_mcp`

With this integration:
- Sentry issues link to commit history and suspect commits
- GitHub commits reference Sentry issues in the sidebar

## Verification

```bash
SENTRY_DSN="<dsn>" python3 -c "
from anthropic_news_mcp.sentry import init_sentry
init_sentry()
print('Sentry initialized')
"
```

## Disabling

Unset `SENTRY_DSN` or set it to an empty string:
```bash
unset SENTRY_DSN
```
