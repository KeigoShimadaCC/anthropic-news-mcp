# Tooling

The repo's tooling is small and consistent: ruff for lint and format, mypy for typing, pytest for tests, pre-commit for local enforcement, and three GitHub Actions workflows.

## Ruff

`ruff.toml`:

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM"]
ignore = ["E501"]

[lint.isort]
known-first-party = ["anthropic_news_mcp"]

[format]
quote-style = "double"
indent-style = "space"
```

Selected rule families:

- `E`, `W` — pycodestyle errors / warnings
- `F` — pyflakes
- `I` — isort import ordering
- `N` — pep8-naming
- `UP` — pyupgrade (modern syntax)
- `B` — bugbear (likely bugs)
- `SIM` — flake8-simplify

`E501` (line too long) is ignored because long string literals (multi-line tool descriptions, regexes) are common.

Run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format .
.venv/bin/ruff format --check .   # dry run; CI uses this
```

## Mypy

`mypy.ini`:

```ini
[mypy]
python_version = 3.11
strict = True
warn_return_any = True
warn_unused_configs = True
exclude = ["evals/"]
```

Strict mode is scoped to source code, not the eval harness. CI runs:

```bash
mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
```

Notes:

- Tests are not strict-typed; the strict run is scoped to `src/`.
- Optional dependencies (`anthropic`, `jwt`, `starlette`) are imported lazily and guarded with `try/except ImportError` or `TYPE_CHECKING`.

## Pytest

Configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

See [Testing](./testing.md).

## Pre-commit

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff-check
      - id: ruff-format

  - repo: local
    hooks:
      - id: mypy-strict
        name: mypy (strict)
        entry: mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py
        ...

      - id: pytest-offline
        name: pytest (offline suite)
        entry: pytest -q
        ...
        stages: [pre-push]
```

Install both stages:

```bash
.venv/bin/pre-commit install                       # per-commit
.venv/bin/pre-commit install --hook-type pre-push  # per-push
```

Per-commit runs `ruff-check`, `ruff-format`, and `mypy --strict`. Per-push adds the offline pytest suite. Skip a hook with `git commit --no-verify` if you really need to.

## GitHub Actions

Three workflows in `.github/workflows/`.

### `ci.yml`

Triggers on `push` to `main`/`master` and on every `pull_request`.

Steps:

1. Set up Python 3.11 and `uv`.
2. `uv pip install -e ".[dev]" --system`.
3. Smoke test import: `python -c "from anthropic_news_mcp.server import mcp; print('import ok')"`.
4. `ruff check .`
5. `ruff format --check .`
6. `mypy --strict src/anthropic_news_mcp/*.py src/anthropic_news_mcp/fetchers/*.py`
7. `pytest -q`
8. `python evals/run_offline_eval.py`

Caching: `astral-sh/setup-uv@v3` with `enable-cache: true` and `cache-dependency-glob: pyproject.toml`.

### `security.yml`

Triggers on `push`, `pull_request`, weekly cron (`17 3 * * 1`), and `workflow_dispatch`.

Two jobs:

- **CodeQL** — runs `github/codeql-action/init@v3` for Python, then autobuild and analyze. Always runs.
- **Dependency audit** — runs `pip-audit`. Only on schedule or manual trigger; not on push/PR (to avoid PR noise from third-party CVEs).

### `eval.yml`

Triggers on `workflow_dispatch` only. Runs the LLM eval harness with `ANTHROPIC_API_KEY` from secrets. Manual-only because each run costs ~$0.15.

## Dependabot

`.github/dependabot.yml` configures weekly checks for both `pip` and `github-actions` ecosystems with up to 10 open PRs each.

## Branch protection

The README documents target state for the default branch:

- Require pull requests before merge
- At least 1 approval
- Required status checks: `lint-and-test` and `CodeQL`
- Restrict direct pushes by non-admin contributors
- Enforce admins

These are not currently enforced via repo settings (since this is a single-maintainer project) but the policy is documented.

## Issue and PR templates

`.github/ISSUE_TEMPLATE/` has bug-report and feature-request forms with `config.yml` disabling blank issues. `.github/pull_request_template.md` provides a checklist for PRs.

## Devcontainer

`.devcontainer/devcontainer.json` makes the repo open cleanly in a VS Code dev container. Opening it auto-installs `.[dev]`.

## Editor config

There's no `.editorconfig`. The project relies on `ruff format` (or your editor's ruff plugin) for formatting consistency.
