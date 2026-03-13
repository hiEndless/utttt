#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_regression.sh

Description:
  CI regression 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、event-center quick 回归链路与语义审计。

Environment:
  MAX_AGENT_READYZ_LEVEL        agent readyz 最大允许级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS  decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT  pipeline_mode unknown 计数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_MISSING_COUNT  pipeline_mode 缺失计数上限（默认 -1 忽略）
  REQUIRE_AGENT_READYZ_REPORT   是否要求 readyz 报告存在（1/0，默认 1）
  AGENT_READYZ_BASE_URL         agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S        agent readyz 拉取超时秒数（默认 2.0）

Failure Codes:
  exit 1  任一守卫/测试失败
USAGE
  exit 0
fi

if (($# > 0)); then
  echo "[failed] unsupported args: $*"
  echo "hint: run 'bash tools/ci/verify_regression.sh --help'"
  exit 1
fi

SUMMARY_PATH="verification/reports/summary.latest.json"

echo "[regression 1/13] structure guard"
bash tools/local/check_structure.sh
echo "[regression 2/13] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[regression 3/13] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[regression 4/13] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[regression 5/13] ci help smoke tests"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q verification/text/test_verify_ci_help.py
else
  python3 -m pytest -q verification/text/test_verify_ci_help.py
fi
echo "[regression 6/13] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[regression 7/13] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh
echo "[regression 8/13] quick verification suite"
bash tools/ci/verify_all.sh --event-center-quick --report-json=verification/reports/regression.latest.json
echo "[regression 9/13] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[regression 10/13] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[regression 11/13] semantic audit"
bash tools/local/audit_semantics.sh
echo "[regression 12/13] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
echo "[regression 13/13] aggregate and check"
MAX_AGENT_READYZ_LEVEL="${MAX_AGENT_READYZ_LEVEL:-red}"
MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:--1}"
MAX_PIPELINE_MODE_UNKNOWN_COUNT="${MAX_PIPELINE_MODE_UNKNOWN_COUNT:--1}"
MAX_PIPELINE_MODE_MISSING_COUNT="${MAX_PIPELINE_MODE_MISSING_COUNT:--1}"
REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-1}"
AGENT_READYZ_BASE_URL="${AGENT_READYZ_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
echo "[regression] MAX_AGENT_READYZ_LEVEL=$MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REQUIRE_AGENT_READYZ_REPORT"
echo "[regression] MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
echo "[regression] MAX_PIPELINE_MODE_UNKNOWN_COUNT=$MAX_PIPELINE_MODE_UNKNOWN_COUNT MAX_PIPELINE_MODE_MISSING_COUNT=$MAX_PIPELINE_MODE_MISSING_COUNT"
REGRESSION_ARGS=(
  --with-pipeline-mode-report
  --with-agent-readyz
  --summary-path "$SUMMARY_PATH"
  --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
  --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
  --max-agent-readyz-level "$MAX_AGENT_READYZ_LEVEL"
  --max-decision-trace-schema-guard-invalid-records "$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
  --max-pipeline-mode-unknown-count "$MAX_PIPELINE_MODE_UNKNOWN_COUNT"
  --max-pipeline-mode-missing-count "$MAX_PIPELINE_MODE_MISSING_COUNT"
)
if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
  REGRESSION_ARGS+=(--require-agent-readyz-report)
fi
bash tools/local/aggregate_and_check.sh "${REGRESSION_ARGS[@]}"
if [[ -f "$SUMMARY_PATH" ]]; then
  python3 - "$SUMMARY_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

legacy = int(payload.get("pipeline_mode_legacy_count") or 0)
minimal = int(payload.get("pipeline_mode_minimal_count") or 0)
unknown = int(payload.get("pipeline_mode_unknown_count") or 0)
missing = int(payload.get("pipeline_mode_missing_count") or 0)
legacy_ratio = float(payload.get("pipeline_mode_legacy_ratio") or 0.0)
minimal_ratio = float(payload.get("pipeline_mode_minimal_ratio") or 0.0)
print(
    "[regression] pipeline_mode_summary "
    f"legacy={legacy} minimal={minimal} unknown={unknown} missing={missing} "
    f"legacy_ratio={legacy_ratio:.6f} minimal_ratio={minimal_ratio:.6f}"
)
PY
fi
