#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_nightly.sh

Description:
  CI nightly 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、全量报告回归链路与语义聚合校验。

Environment:
  MAX_LEGACY_CONFIDENCE_RATIO   execution legacy confidence 占比上限（默认 0.05）
  MAX_AGENT_READYZ_LEVEL        agent readyz 最大允许级别（默认 yellow）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS  decision_trace schema guard invalid 记录数上限（默认 0）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT  pipeline_mode unknown 计数上限（默认 0）
  MAX_PIPELINE_MODE_MISSING_COUNT  pipeline_mode 缺失计数上限（默认 0）
  MAX_EVENT_TYPE_MATCH_MISSING_COUNT  event_type_match 缺失计数上限（默认 0）
  MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT  event_type_match unknown 计数上限（默认 0）
  MIN_EVENT_TYPE_MATCH_ALIAS_RATIO  event_type_match alias 占比下限（默认 -1 忽略）
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
  echo "hint: run 'bash tools/ci/verify_nightly.sh --help'"
  exit 1
fi

SUMMARY_PATH="verification/reports/summary.latest.json"

echo "[nightly 1/12] structure guard"
bash tools/local/check_structure.sh
echo "[nightly 2/12] script whitelist guard"
bash tools/local/check_script_compat_whitelist.sh
echo "[nightly 3/12] new_arch help snapshot guard"
bash tools/local/check_new_arch_guards_help_snapshot_guard.sh
echo "[nightly 4/12] cli help snapshot guard"
bash tools/local/check_cli_help_snapshot_guard.sh
echo "[nightly 5/12] contract docs canonical layout guard"
bash tools/local/check_contract_docs_canonical_layout_guard.sh
echo "[nightly 6/12] pipeline semantic terms doc guard"
bash tools/local/check_pipeline_semantic_terms_doc_guard.sh
echo "[nightly 7/12] full verification suite"
bash tools/ci/verify_all.sh --report-json=verification/reports/nightly.latest.json
echo "[nightly 8/12] provider_state invalid warning->alert chain smoke"
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
echo "[nightly 9/12] sync contract indexes"
bash tools/local/sync_contract_indexes.sh
echo "[nightly 10/12] semantic audit"
bash tools/local/audit_semantics.sh
echo "[nightly 11/12] semantic warning budget"
bash tools/local/check_semantic_warning_budget.sh
echo "[nightly 12/12] aggregate and check"
MAX_LEGACY_CONFIDENCE_RATIO="${MAX_LEGACY_CONFIDENCE_RATIO:-0.05}"
MAX_AGENT_READYZ_LEVEL="${MAX_AGENT_READYZ_LEVEL:-yellow}"
MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:-0}"
MAX_PIPELINE_MODE_UNKNOWN_COUNT="${MAX_PIPELINE_MODE_UNKNOWN_COUNT:-0}"
MAX_PIPELINE_MODE_MISSING_COUNT="${MAX_PIPELINE_MODE_MISSING_COUNT:-0}"
MAX_EVENT_TYPE_MATCH_MISSING_COUNT="${MAX_EVENT_TYPE_MATCH_MISSING_COUNT:-0}"
MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT="${MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT:-0}"
MIN_EVENT_TYPE_MATCH_ALIAS_RATIO="${MIN_EVENT_TYPE_MATCH_ALIAS_RATIO:--1}"
REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-1}"
AGENT_READYZ_BASE_URL="${AGENT_READYZ_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
echo "[nightly] MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
echo "[nightly] MAX_AGENT_READYZ_LEVEL=$MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REQUIRE_AGENT_READYZ_REPORT"
echo "[nightly] MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
echo "[nightly] MAX_PIPELINE_MODE_UNKNOWN_COUNT=$MAX_PIPELINE_MODE_UNKNOWN_COUNT MAX_PIPELINE_MODE_MISSING_COUNT=$MAX_PIPELINE_MODE_MISSING_COUNT"
echo "[nightly] MAX_EVENT_TYPE_MATCH_MISSING_COUNT=$MAX_EVENT_TYPE_MATCH_MISSING_COUNT MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT=$MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT MIN_EVENT_TYPE_MATCH_ALIAS_RATIO=$MIN_EVENT_TYPE_MATCH_ALIAS_RATIO"
NIGHTLY_ARGS=(
  --with-pipeline-mode-report
  --with-event-type-match-report
  --with-agent-readyz
  --summary-path "$SUMMARY_PATH"
  --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
  --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
  --max-legacy-confidence-ratio "$MAX_LEGACY_CONFIDENCE_RATIO"
  --max-agent-readyz-level "$MAX_AGENT_READYZ_LEVEL"
  --max-decision-trace-schema-guard-invalid-records "$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
  --max-pipeline-mode-unknown-count "$MAX_PIPELINE_MODE_UNKNOWN_COUNT"
  --max-pipeline-mode-missing-count "$MAX_PIPELINE_MODE_MISSING_COUNT"
  --max-event-type-match-missing-count "$MAX_EVENT_TYPE_MATCH_MISSING_COUNT"
  --max-event-type-match-unknown-count "$MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT"
  --min-event-type-match-alias-ratio "$MIN_EVENT_TYPE_MATCH_ALIAS_RATIO"
)
if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
  NIGHTLY_ARGS+=(--require-agent-readyz-report)
fi
bash tools/local/aggregate_and_check.sh "${NIGHTLY_ARGS[@]}"
bash tools/local/print_pipeline_mode_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_event_type_match_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
