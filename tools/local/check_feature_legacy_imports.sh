#!/usr/bin/env bash
set -euo pipefail

STRICT=0
if [[ "${1:-}" == "--strict" ]]; then
  STRICT=1
fi

PATTERN='(^|[[:space:]])(from|import)[[:space:]]+feature_service\.(app|routes|service|contracts|providers|ports|normalizers)([[:space:]]|$|[.,])'

# 仅扫描业务与工具代码，排除文档与 feature_service 兼容层本身。
RESULTS="$(rg -n -S "$PATTERN" \
  --glob '!feature_service/**' \
  --glob '!**/*.md' \
  --glob '!**/__pycache__/**' \
  --glob '!venv/**' \
  . || true)"

if [[ -z "$RESULTS" ]]; then
  echo "[passed] no legacy feature_service wrapper imports outside feature_service/"
  exit 0
fi

echo "[warn] detected legacy feature_service wrapper imports outside feature_service/:"
echo "$RESULTS"

if [[ "$STRICT" -eq 1 ]]; then
  echo "[failed] strict mode enabled"
  exit 1
fi

echo "[warn] non-strict mode: report only"
