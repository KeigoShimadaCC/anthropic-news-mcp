# Agent-Readiness Report

| Field | Value |
|-------|-------|
| Repository | https://github.com/KeigoShimadaCC/anthropic-news-mcp.git |
| Branch | `main` |
| Commit | `458bc15ec7ff7fbbefe55c75307e2a7300604b2f` |
| Generated | 2026-05-08 |
| Report ID | `251af545-2ff4-4b9d-86a0-f130c37a0460` |
| Previous report | `380c6c6a-a944-4d9d-9c2f-8d538e4ef98f` (Level 4, 65.6%) |
| Level | **Level 5** (80–100% pass rate) |
| Pass rate | ≈ 95.7% across 70 non-skipped signals |

View the full interactive report: https://app.factory.ai/analytics/readiness/https%253A%252F%252Fgithub.com%252Fkeigoshimadacc%252Fanthropic-news-mcp

## Applications

1. `.` — Python MCP server (FastMCP/SQLite) aggregating Anthropic news, model releases, and community signals from 17 configured sources, exposing 15 MCP tools, 7 resources, and 6 prompts. Now with Sentry, structured metrics, feature flags, tenacity retries, and full CI quality gates.

## Criteria

### Style & Validation

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| lint_config | 1/1 | ruff with E/F/I/N/W/UP/B/SIM/FIX rulesets in `ruff.toml` |
| type_check | 1/1 | `mypy.ini` strict=True; CI enforces `mypy --strict` |
| formatter | 1/1 | `ruff format` configured and CI-checked |
| pre_commit_hooks | 1/1 | `.pre-commit-config.yaml` with check-added-large-files, ruff, mypy, pytest pre-push |
| strict_typing | 1/1 | mypy strict mode |
| naming_consistency | 1/1 | ruff `N` (pep8-naming) ruleset |
| cyclomatic_complexity | 1/1 | `radon cc src/ -n F` hard gate in CI |
| large_file_detection | 1/1 | pre-commit `check-added-large-files --maxkb=500` |
| dead_code_detection | 1/1 | `vulture src/ vulture_whitelist.py --min-confidence 80` in CI |
| duplicate_code_detection | 1/1 | `pylint --enable=duplicate-code --min-similarity-lines=10` in CI |
| code_modularization | skipped | Small project; no architectural fitness functions |
| tech_debt_tracking | 1/1 | CI counts TODO/FIXME/HACK/XXX into step summary; ruff FIX rule |
| n_plus_one_detection | skipped | SQLite cache without ORM |

### Build System

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| build_cmd_doc | 1/1 | README + AGENTS.md + CLAUDE.md document install/run |
| deps_pinned | 1/1 | `uv.lock` committed |
| vcs_cli_tools | 1/1 | `gh` CLI authenticated |
| automated_pr_review | 1/1 | `pr-review.yml` posts ruff/mypy/test review comments |
| agentic_development | 1/1 | Claude trailers; AGENTS.md, CLAUDE.md, `.claude/skills/add-source.md`; Copilot reviews |
| fast_ci_feedback | 1/1 | Recent CI run end-to-end ≈ 69 sec |
| build_performance_tracking | 1/1 | uv cache; `pytest --durations=10`; pdoc artifact upload |
| deployment_frequency | 0/1 | `release.yml` exists but no tags pushed yet |
| single_command_setup | 1/1 | `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` |
| feature_flag_infrastructure | 1/1 | `src/anthropic_news_mcp/flags.py` env-driven `FeatureFlags` |
| release_notes_automation | 1/1 | `release.yml` generates changelog from git log |
| progressive_rollout | skipped | Not infra repo |
| rollback_automation | skipped | No deployment pipeline |
| monorepo_tooling | skipped | Single-application repo |
| heavy_dependency_detection | skipped | Backend/CLI service |
| unused_dependencies_detection | 1/1 | `deptry src/` in CI; `[tool.deptry]` config |
| version_drift_detection | skipped | Single-application repo |
| release_automation | 1/1 | `release.yml` builds + publishes GitHub Releases on `v*` tag |
| dead_feature_flag_detection | 0/1 | No stale-flag detector for env-var flags |

### Testing

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| unit_tests_exist | 1/1 | 209 tests collected |
| integration_tests_exist | 1/1 | `test_remote.py`, `test_server.py` |
| unit_tests_runnable | 1/1 | Verified via `pytest --collect-only` |
| test_performance_tracking | 1/1 | `addopts=--durations=10` in pyproject |
| flaky_test_detection | skipped | No retry/quarantine tooling |
| test_coverage_thresholds | 1/1 | `--cov-fail-under=80`; `.codecov.yml` 80% target |
| test_naming_conventions | 1/1 | pytest testpaths + `test_*.py` convention |
| test_isolation | 1/1 | `set_db_path(tmp_path)` autouse fixture; pytest-asyncio |

### Documentation

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| agents_md | 1/1 | `AGENTS.md` (6,197 bytes) at root with Quick Start, Architecture, runbook refs |
| readme | 1/1 | Comprehensive `README.md` |
| automated_doc_generation | 1/1 | CI runs `pdoc src/anthropic_news_mcp -o docs/api`; `docs/api/*.html` committed |
| skills | 1/1 | `.claude/skills/add-source.md` skill guide |
| documentation_freshness | 1/1 | README/AGENTS/CLAUDE all modified in last 24 hours |
| api_schema_docs | 1/1 | `docs/schema.json` JSON Schema for tools/resources/prompts |
| service_flow_documented | 1/1 | README ASCII + droid-wiki Mermaid diagrams |
| agents_md_validation | 0/1 | No automated AGENTS.md command validation |

### Dev Environment

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| devcontainer | 1/1 | `.devcontainer/devcontainer.json` Python 3.11 + ruff extension |
| env_template | 1/1 | `.env.example` with feature flags, Sentry DSN, remote ASGI vars |
| local_services_setup | skipped | SQLite-only; no external service deps |
| database_schema | 1/1 | `cache.py` defines full SQLite schema |
| devcontainer_runnable | skipped | devcontainer CLI not verified |

### Debugging & Observability

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| structured_logging | 1/1 | `logging.getLogger` across modules; `metrics.py` emits structured records |
| distributed_tracing | 1/1 | `x-request-id` propagation in remote ASGI |
| metrics_collection | 1/1 | `metrics.py` emits structured counters/timers, flag-gated |
| code_quality_metrics | 1/1 | Codecov upload; `.codecov.yml` 80% target; CodeQL active |
| error_tracking_contextualized | 1/1 | `sentry.py` with DSN-gated init; `[observability]` extra |
| alerting_configured | 1/1 | `alert.yml` opens GitHub issues on CI failure |
| runbooks_documented | 1/1 | `docs/runbooks/cache-reset.md`, `sentry-setup.md`, `source-failure.md` |
| deployment_observability | 0/1 | No dashboard links / Slack deploy webhooks |
| health_checks | 1/1 | MCP `ping` tool |
| circuit_breakers | 1/1 | tenacity retry/backoff in `retrieval.py` |
| profiling_instrumentation | skipped | No APM configured |

### Security

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| branch_protection | 1/1 | `main` protected: required reviews + status checks + linear history + admin enforcement |
| secret_scanning | 1/1 | GitHub native enabled + CodeQL workflow |
| codeowners | 1/1 | `.github/CODEOWNERS` valid |
| automated_security_review | 1/1 | CodeQL on push/PR; pip-audit scheduled; pr-review.yml comments |
| dependency_update_automation | 1/1 | Both `dependabot.yml` and `renovate.json` configured |
| gitignore_comprehensive | 1/1 | Excludes .env, build artifacts, IDE configs, OS files |
| dast_scanning | skipped | Not deployed as web service |
| pii_handling | skipped | Public web content only |
| privacy_compliance | skipped | No end-user data collection |
| secrets_management | 1/1 | GitHub Actions secrets; .env gitignored; OIDC JWT for remote |
| log_scrubbing | 1/1 | `_sanitize_error` redacts Bearer/api_key/password/token |
| min_release_age | 1/1 | `renovate.json` `minimumReleaseAge: "3 days"` |
| issue_templates | 1/1 | bug_report.yml + feature_request.yml + config.yml |
| issue_labeling_system | 1/1 | `.github/labels.yml` (8 labels) + sync workflow |
| backlog_health | skipped | No open issues |
| pr_templates | 1/1 | `.github/pull_request_template.md` present |
| product_analytics_instrumentation | 0/1 | No Mixpanel/Amplitude/PostHog/Heap/GA4 |
| error_to_insight_pipeline | 1/1 | `alert.yml` auto-issues from CI failures + Sentry SDK |

## Summary

| Category | Passing | Failing | Skipped |
|----------|---------|---------|---------|
| Style & Validation | 11 | 0 | 2 |
| Build System | 13 | 2 | 6 |
| Testing | 7 | 0 | 1 |
| Documentation | 7 | 1 | 0 |
| Dev Environment | 3 | 0 | 2 |
| Debugging & Observability | 9 | 1 | 1 |
| Security | 13 | 1 | 4 |
| **Total** | **63** | **5** | **16** |

Pass rate ≈ **95.7%** across 70 non-skipped signals → **Level 5**.

## Remaining gaps (5)

1. **deployment_frequency** — `release.yml` is built but no tags have been pushed.
2. **dead_feature_flag_detection** — env-var flags but no stale-flag detector.
3. **agents_md_validation** — no CI step verifying AGENTS.md commands still work.
4. **deployment_observability** — no monitoring dashboard links / deploy webhooks.
5. **product_analytics_instrumentation** — no end-user analytics SDK (rarely meaningful for an MCP server).

## Action Items

Three high-impact next steps:

1. **Cut a v0.1.0 git tag** to exercise `release.yml`. The release pipeline is built; it just needs traffic to satisfy `deployment_frequency`.
2. **Add an AGENTS.md validator step in CI.** Parse the bash blocks and execute them in a smoke job, or add a markdown link checker, to close `agents_md_validation`.
3. **Wire deploy/dashboard pointers.** Add a `docs/dashboards.md` (or a `## Operations` README section) linking to the Sentry org/project URL — satisfies `deployment_observability` for an ops-light project.

## Changes since previous report

- **Default branch:** `master` → `main`.
- **Level:** 4 (65.6%) → **5 (~95.7%)**. 16 criteria flipped 0→1.

| Criterion | Before | After | Reason |
|-----------|--------|-------|--------|
| agents_md | 0/1 | 1/1 | `AGENTS.md` added |
| agents_md_validation | skipped | 0/1 | Now applicable; no validator |
| api_schema_docs | 0/1 | 1/1 | `docs/schema.json` committed |
| automated_doc_generation | 0/1 | 1/1 | `pdoc` in CI; `docs/api/*.html` |
| automated_pr_review | 0/1 | 1/1 | `pr-review.yml` posts comments |
| alerting_configured | 0/1 | 1/1 | `alert.yml` |
| circuit_breakers | 0/1 | 1/1 | tenacity |
| code_quality_metrics | 0/1 | 1/1 | Codecov |
| cyclomatic_complexity | 0/1 | 1/1 | radon |
| dead_code_detection | 0/1 | 1/1 | vulture |
| dead_feature_flag_detection | skipped | 0/1 | Now applicable |
| deps_pinned | 0/1 | 1/1 | `uv.lock` committed |
| duplicate_code_detection | 0/1 | 1/1 | pylint duplicate-code |
| error_to_insight_pipeline | 0/1 | 1/1 | alert.yml + Sentry |
| error_tracking_contextualized | 0/1 | 1/1 | `sentry.py` |
| fast_ci_feedback | skipped | 1/1 | CI ~69s |
| feature_flag_infrastructure | 0/1 | 1/1 | `flags.py` |
| issue_labeling_system | 0/1 | 1/1 | `labels.yml` |
| large_file_detection | 0/1 | 1/1 | pre-commit hook |
| metrics_collection | 0/1 | 1/1 | `metrics.py` |
| min_release_age | 0/1 | 1/1 | renovate minimumReleaseAge |
| release_automation | 0/1 | 1/1 | `release.yml` |
| release_notes_automation | 0/1 | 1/1 | `release.yml` changelog |
| runbooks_documented | 0/1 | 1/1 | `docs/runbooks/` |
| skills | 0/1 | 1/1 | `.claude/skills/add-source.md` |
| tech_debt_tracking | 0/1 | 1/1 | CI grep + FIX rule |
| test_coverage_thresholds | 0/1 | 1/1 | `--cov-fail-under=80` |
| test_performance_tracking | 0/1 | 1/1 | `--durations=10` |
| unused_dependencies_detection | 0/1 | 1/1 | deptry |
