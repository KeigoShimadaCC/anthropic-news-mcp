# Deployment & Observability Dashboards

Quick-reference links for operating the anthropic-news-mcp server.

## Deployment History

| Link | Description |
|------|-------------|
| [GitHub Releases](https://github.com/KeigoShimadaCC/anthropic-news-mcp/releases) | All tagged releases with changelogs and built assets |
| [CI Runs](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/ci.yml) | Latest CI pass/fail status |
| [Security Scans](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions/workflows/security.yml) | CodeQL + pip-audit results |

## Code Quality

| Link | Description |
|------|-------------|
| [Codecov](https://codecov.io/gh/KeigoShimadaCC/anthropic-news-mcp) | Coverage reports and trend over time |
| [CI Artifacts](https://github.com/KeigoShimadaCC/anthropic-news-mcp/actions) | Coverage XML + API docs uploaded on every CI run |

## Error Tracking (Sentry)

Set up Sentry by following `docs/runbooks/sentry-setup.md`. Once configured:

| Link | Description |
|------|-------------|
| Sentry Project | `https://sentry.io/organizations/<org>/projects/anthropic-news-mcp/` |
| Sentry Issues | `https://sentry.io/organizations/<org>/issues/?project=<id>` |

Replace `<org>` and `<id>` with your Sentry organization slug and project ID after setup.

## Alerting

- **CI failures on main** → GitHub Issues auto-created by [`alert.yml`](../.github/workflows/alert.yml) with label `ci`
- **Filter**: [Open CI issues](https://github.com/KeigoShimadaCC/anthropic-news-mcp/issues?q=is%3Aopen+label%3Aci)

## Source Health

Run the audit CLI for a live health snapshot:

```bash
# All sources
.venv/bin/anthropic-news-audit

# Single source
.venv/bin/anthropic-news-audit --sources anthropic-newsroom

# JSON output
.venv/bin/anthropic-news-audit --json /tmp/audit.json
```
