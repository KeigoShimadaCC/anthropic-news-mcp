#!/usr/bin/env bash
# Generate API documentation with pdoc into docs/api/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${REPO_ROOT}/docs/api"

echo "Generating API docs → ${OUT}"
pdoc "${REPO_ROOT}/src/anthropic_news_mcp" -o "${OUT}" --docformat google
echo "Done. Open ${OUT}/anthropic_news_mcp.html to view."
