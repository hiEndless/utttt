#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
if [[ "$MODE" == "--help" || "$MODE" == "-h" ]]; then
  cat <<'EOF'
用法:
  bash scripts/check_event_center_contract_guards.sh
  bash scripts/check_event_center_contract_guards.sh --quick
EOF
  exit 0
fi

if [[ "$MODE" == "--quick" ]]; then
  echo "[1/2] event_center 契约/Schema 守卫（quick）"
  bash scripts/check_event_center_contract_schema_guards.sh --quick

  echo "[2/2] event_center Runtime 守卫（quick）"
  bash scripts/check_event_center_runtime_family_guards.sh --quick
  echo "[通过] event_center 契约守卫检查完成（quick）。"
  exit 0
fi

if [[ "$MODE" != "all" ]]; then
  echo "[失败] 不支持的参数: $MODE"
  echo "使用 --help 查看可用参数。"
  exit 1
fi

echo "[1/3] event_center 契约/Schema 守卫（全量）"
bash scripts/check_event_center_contract_schema_guards.sh

echo "[2/3] event_center Runtime 守卫（全量）"
bash scripts/check_event_center_runtime_family_guards.sh

echo "[3/3] event_center 守卫接线检查（全量）"
bash scripts/check_event_center_guard_wiring.sh

echo "[通过] event_center 契约守卫检查完成。"
