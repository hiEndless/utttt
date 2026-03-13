#!/usr/bin/env bash
set -euo pipefail

SCRIPT="tools/local/run_agent_execution_closed_loop_smoke.sh"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/check_agent_execution_closed_loop_smoke.sh

Description:
  运行最小闭环 smoke 的三种模式并校验退出码：
  accept->0 / reject->0 / error->2
USAGE
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  print_help
  exit 0
fi

if (($# > 0)); then
  echo "[失败] 不支持的参数: $*" >&2
  print_help
  exit 1
fi

run_mode() {
  local mode="$1"
  local expect="$2"
  local code=0
  set +e
  bash "$SCRIPT" --result-mode "$mode" >/tmp/agent_closed_loop_"$mode".json
  code=$?
  set -e
  if [[ "$code" != "$expect" ]]; then
    echo "[失败] mode=$mode expect_exit=$expect actual_exit=$code" >&2
    return 1
  fi
  echo "[ok] mode=$mode exit=$code"
}

run_mode "accept" "0"
run_mode "reject" "0"
run_mode "error" "2"
echo "[ok] closed loop smoke exits verified"

