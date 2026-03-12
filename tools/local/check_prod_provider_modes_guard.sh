#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
  cat <<'EOF'
用法：
  bash tools/local/check_prod_provider_modes_guard.sh

说明：
  统一校验 agent/execution 在 prod profile 下禁止使用 stub/mock/noop provider 的门禁约束。
EOF
  exit 0
fi

echo "[1/2] 校验 agent prod provider 门禁"
./venv/bin/pytest -q verification/auditors/agent_server_new/test_bootstrap.py

echo "[2/2] 校验 execution prod provider/sink 门禁"
./venv/bin/pytest -q verification/validators/execution_service/test_execution_app_provider_mode.py

echo "[通过] prod provider modes 守卫检查完成。"
