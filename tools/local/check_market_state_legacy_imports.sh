#!/usr/bin/env bash
set -euo pipefail

STRICT=0
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

PATTERN='(^|[[:space:]])(from|import)[[:space:]]+market_state_engine\.(app|routes|service|contracts|errors|engine|msl|adapters|ports|factors|state_inference)([[:space:]]|$|[.,])'

# 仅扫描业务与工具代码，排除文档、旧兼容层本身与 pycache。
RESULTS="$(rg -n -S "$PATTERN" \
  --glob '!market_state_engine/**' \
  --glob '!**/*.md' \
  --glob '!**/__pycache__/**' \
  --glob '!venv/**' \
  . || true)"

if [[ -z "$RESULTS" ]]; then
  echo "[passed] no legacy market_state_engine wrapper imports outside market_state_engine/"
  exit 0
fi

echo "[warn] detected legacy market_state_engine wrapper imports outside market_state_engine/:"
echo "$RESULTS"

if [[ "$STRICT" -eq 1 ]]; then
  echo "[failed] strict mode enabled"
  exit 1
fi

echo "[warn] non-strict mode: report only"
