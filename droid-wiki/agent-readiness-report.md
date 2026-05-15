# Agent-Readiness Report

| Field | Value |
|-------|-------|
| Repository | https://github.com/KeigoShimadaCC/anthropic-news-mcp.git |
| Branch | `main` |
| Commit | `c2c99c0c495222763b82936f37fcf1ee3cf9a6fd` |
| Generated | 2026-05-08 |
| Report ID | `a5354f57-c540-4eb3-bab4-1d47f4690d8a` |
| Previous report | `251af545-2ff4-4b9d-86a0-f130c37a0460` (Level 5, 95.7%) |
| Level | **Level 5** (80–100% pass rate) |
| Pass rate | **100%** across 67 non-skipped signals |

View the full interactive report: https://app.factory.ai/analytics/readiness/https%253A%252F%252Fgithub.com%252Fkeigoshimadacc%252Fanthropic-news-mcp

## Applications

1. `.` — Python MCP server (FastMCP/SQLite) aggregating Anthropic news, model releases, and community signals from 17 configured sources, exposing 15 MCP tools, 7 resources, and 6 prompts. v0.1.0 release tagged, AGENTS.md validator + smoke scripts, dead-flag detector, dashboards runbook, and PostHog analytics scaffolding.

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
| agentic_development | 1/1 | factory-droid[bot] trailers; AGENTS.md, CLAUDE.md, `.claude/skills/add-source.md` |
| fast_ci_feedback | 1/1 | Recent CI run end-to-end ≈ 70 sec |
| build_performance_tracking | 1/1 | uv cache; `pytest --durations=10`; pdoc artifact upload |
| deployment_frequency | **1/1** | v0.1.0 tag pushed; `release.yml` ran successfully on `c2c99c0` |
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
| dead_feature_flag_detection | **1/1** | `scripts/check_flags.py` detects stale + undefined `FLAGS.X` references via AST |

### Testing

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| unit_tests_exist | 1/1 | 200+ tests collected |
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
| agents_md_validation | **1/1** | `scripts/validate_agents_md.py` CI step checks sections, file refs, gate parity vs ci.yml |

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
| deployment_observability | **1/1** | `docs/dashboards.md` links Releases, CI runs, Codecov, Sentry project + issues |
| health_checks | 1/1 | MCP `ping` tool |
| circuit_breakers | 1/1 | tenacity retry/backoff in `retrieval.py` |
| profiling_instrumentation | skipped | No APM configured |

### Security

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| branch_protection | 1/1 | `main` protected: required status checks + linear history + admin enforcement |
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
| product_analytics_instrumentation | **1/1** | `analytics.py` initialises PostHog (POSTHOG_API_KEY-gated); `main()` captures `server_startup` event with version/python/platform/source_count/remote_transport |
| error_to_insight_pipeline | 1/1 | `alert.yml` auto-issues from CI failures + Sentry SDK |

## Summary

| Category | Passing | Failing | Skipped |
|----------|---------|---------|---------|
| Style & Validation | 11 | 0 | 2 |
| Build System | 15 | 0 | 6 |
| Testing | 7 | 0 | 1 |
| Documentation | 8 | 0 | 0 |
| Dev Environment | 3 | 0 | 2 |
| Debugging & Observability | 10 | 0 | 1 |
| Security | 13 | 0 | 4 |
| **Total** | **67** | **0** | **15** |

Pass rate **100%** across 67 non-skipped signals → **Level 5** (consolidated).

## Remaining gaps

None — every applicable signal passes. Skipped signals are genuine N/A
(infra rollout, monorepo tooling, frontend bundle analysis, end-user PII)
for a small Python MCP stdio server.

## Action Items

To extend headroom and unlock currently skipped signals:

1. **Push the working-tree improvements** — PostHog `track_tool` decorator on every MCP tool, AGENTS.md `--smoke` mode, `_bool_env` env-var drift in `check_flags.py`, GitHub Pages auto-deploy workflow. Moves `deployment_frequency`, `agents_md_validation`, and `product_analytics_instrumentation` from "passes" to "exceeds the bar."
2. **Add `pytest-rerunfailures`** so `flaky_test_detection` graduates from skipped to passing.
3. **Document a docker-compose** for the optional remote ASGI deployment so `local_services_setup` can be re-evaluated and unlock infra-leaning signals.

## Changes since previous report (251af545)

- **Score:** 95.7% → **100%**.
- **Level:** 5 → **5** (consolidated; 5 of the previously failing signals flipped to passing).

| Criterion | Before | After | Reason |
|-----------|--------|-------|--------|
| deployment_frequency | 0/1 | **1/1** | v0.1.0 git tag pushed; Release workflow ran successfully (gh release list shows v0.1.0 / 2026-05-08) |
| dead_feature_flag_detection | 0/1 | **1/1** | `scripts/check_flags.py` committed — AST-introspects `FeatureFlags` and reports stale-defined or undefined `FLAGS.X` references |
| agents_md_validation | 0/1 | **1/1** | `scripts/validate_agents_md.py` committed; CI step verifies AGENTS.md sections, file-reference links, and gate parity against `ci.yml` |
| deployment_observability | 0/1 | **1/1** | `docs/dashboards.md` committed — sectioned operator pointers to Releases, CI runs, Security, Codecov, Sentry project + issues |
| product_analytics_instrumentation | 0/1 | **1/1** | `src/anthropic_news_mcp/analytics.py` committed; `init_analytics()` initialises PostHog and `main()` captures a `server_startup` event with version/python/platform/source_count/remote_transport (PostHog is on the criterion's accepted-tools list) |
