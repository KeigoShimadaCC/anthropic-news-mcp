# Dependencies

All dependencies are declared in `pyproject.toml`. The runtime surface is intentionally small.

## Required runtime

```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.27",
    "httpx>=0.27.0",
    "selectolax>=0.3.21",
    "pydantic>=2.7.0",
]
```

| Package | Purpose |
|---------|---------|
| `mcp>=1.27` | MCP framework (FastMCP). Provides `mcp.server.fastmcp.FastMCP`, `mcp.types`, the auth provider interface, and Streamable HTTP transport. |
| `httpx>=0.27` | Async HTTP client. Used by every fetcher and by the content extraction layer. |
| `selectolax>=0.3.21` | Fast HTML parser used by every Anthropic listing parser. |
| `pydantic>=2.7` | Models and validation. Pydantic v2 features (`StrEnum`, `model_validator(mode="after")`) are used throughout. |

## Optional `[eval]` extra

```toml
eval = ["anthropic>=0.40.0", "PyYAML>=6.0.0"]
```

| Package | Purpose |
|---------|---------|
| `anthropic` | Used by `evals/run_eval.py` to call `claude-haiku-4-5` for both prompt execution and judging. |
| `PyYAML` | Used by `evals/run_eval.py` and `run_offline_eval.py` to load `golden.yaml` and `offline_cases.yaml`. |

## Optional `[remote]` extra

```toml
remote = [
    "PyJWT[crypto]>=2.8.0",
    "starlette>=0.37.0",
    "uvicorn>=0.30.0",
]
```

| Package | Purpose |
|---------|---------|
| `PyJWT[crypto]` | JWT decode + JWKS client. The `[crypto]` extra pulls in `cryptography` for RS256/ES256 verification. |
| `starlette` | ASGI app, middleware base classes, request/response types. |
| `uvicorn` | The recommended ASGI server. Not strictly required — any ASGI server works. |

## Optional `[dev]` extra

```toml
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.0",
    "PyYAML>=6.0.0",
    "mypy>=1.10.0",
    "ruff>=0.4.0",
    "pre-commit>=3.7.0",
]
```

| Package | Purpose |
|---------|---------|
| `pytest`, `pytest-asyncio` | Test runner and async support. |
| `PyYAML` | Test loaders for the eval YAML files. |
| `mypy` | Strict type checking on `src/`. |
| `ruff` | Lint and format. |
| `pre-commit` | Local git hooks. |

## Build backend

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/anthropic_news_mcp"]
```

`hatchling` is the build backend. There's no setup.py, no setuptools, no MANIFEST.in.

## Console scripts

```toml
[project.scripts]
anthropic-news-mcp = "anthropic_news_mcp.server:main"
anthropic-news-audit = "anthropic_news_mcp.audit:main"
```

Installing the package puts both on `PATH`.

## Removed dependencies

`19c38ff chore: remove unused feedparser and respx dependencies` removed two packages that were added early but never used:

- `feedparser` — RSS feeds turned out to be unnecessary (every source has either a JSON API or a parseable HTML page).
- `respx` — Tests parse fixtures directly instead of mocking HTTP at the `httpx` level.

## Why these dependencies

The runtime surface (4 packages) reflects deliberate scoping:

- **`mcp`** is non-negotiable — it's the protocol the server speaks.
- **`httpx`** is the standard async HTTP client. The shared `get_client()` wraps it.
- **`selectolax`** chosen over `beautifulsoup4` for speed and the simpler CSS-selector API. Anthropic listing pages are large and parsing time matters.
- **`pydantic`** powers both the data model and tool argument validation. Pydantic v2's strict mode aligns with mypy strict mode.

The optional extras keep the install footprint small for clients that only need the stdio surface. A user who runs `pip install anthropic-news-mcp` doesn't pay the cost of `cryptography`, `starlette`, or `uvicorn`.

## Dependabot

`.github/dependabot.yml` opens up to 10 weekly PRs each for `pip` and `github-actions` ecosystems. The dependency-audit workflow (`.github/workflows/security.yml`) runs `pip-audit` on schedule and on manual trigger.
