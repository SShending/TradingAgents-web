#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/web"
npm run build
cd "$ROOT"
exec "${PYTHON:-$ROOT/.venv/bin/python}" -m tradingagents.web
