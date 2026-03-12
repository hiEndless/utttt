#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
用法:
  bash tools/local/check_event_center_runtime_mode_guard.sh

说明:
  校验 event_center 运行模式关键门禁语义：
  1) main runtime: self_check_only / stop_on_error 行为契约
  2) replay runtime: --strict 等价 fail-on-* 组合语义
EOF
  exit 0
fi

echo "[1/2] 校验 runtime 主流程模式门禁"
./venv/bin/pytest -q \
  verification/replay/event_center_new/test_main.py \
  verification/replay/event_center_new/test_runtime_guard_contract.py

echo "[2/2] 校验 replay strict 组合语义"
./venv/bin/pytest -q \
  verification/replay/event_center_new/test_replay_main.py

echo "[通过] event_center runtime mode 守卫检查完成。"
