---
paths:
  - "src/anthropic_news_mcp/flags.py"
  - ".env.example"
---

# Feature flag lifecycle rules

- All boolean env-driven flags live on `FeatureFlags` in `flags.py`. Read via `from .flags import FLAGS` and reference as `FLAGS.<name>`.
- Add and remove flags **atomically across three places**:
  1. Field on the `FeatureFlags` dataclass.
  2. Corresponding `_bool_env("KEY", default)` in `from_env`.
  3. Documented `KEY=…` line in `.env.example`.
- `scripts/check_flags.py` (CI gate) fails on:
  - A flag defined but never referenced (`FLAGS.<name>` not found in source).
  - A reference to a non-existent flag.
  - An env key read by `flags.py` but missing from `.env.example`.
- Remove a flag once it is permanently on. Do not leave dead flags as "configurability".
- Flags are read at import time (`FLAGS = FeatureFlags.from_env()`). Toggling at runtime is not supported.
