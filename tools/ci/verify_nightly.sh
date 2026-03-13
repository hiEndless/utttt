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
  WITH_AGENT_DECISION_AGENT_KEY_REPORT  是否生成 decision_agent_key 路由分布 artifact（1/0，默认 1）
  AGENT_DECISION_AGENT_KEY_REPORT_PATH  decision_agent_key 报告路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT  decision_agent_key unknown 计数上限（默认 0）
  WITH_AGENT_ROUTE_REPLAY_REPORT  是否生成四类来源业务路由回放 artifact（1/0，默认 1）
  AGENT_ROUTE_REPLAY_REPORT_PATH  route replay 报告路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  MAX_ROUTE_REPLAY_MISMATCH_COUNT  route_replay mismatch 计数上限（默认 0）
  MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT  action_hint_semantics mismatch 计数上限（默认 0）
  MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT  action_hint_semantics missing_actual_hint 计数上限（默认 0）
  MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO  action_hint_semantics match_ratio 下限（默认 0.95）
  WITH_AGENT_ACTION_HINT_CASES_REPORT  是否生成 action_hint mismatch 回放 artifact（1/0，默认 1）
  AGENT_ACTION_HINT_CASES_REPORT_PATH  action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH  action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
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
WITH_AGENT_DECISION_AGENT_KEY_REPORT="${WITH_AGENT_DECISION_AGENT_KEY_REPORT:-1}"
AGENT_DECISION_AGENT_KEY_REPORT_PATH="${AGENT_DECISION_AGENT_KEY_REPORT_PATH:-verification/reports/agent_decision_agent_key.latest.json}"
MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="${MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT:-0}"
WITH_AGENT_ROUTE_REPLAY_REPORT="${WITH_AGENT_ROUTE_REPLAY_REPORT:-1}"
AGENT_ROUTE_REPLAY_REPORT_PATH="${AGENT_ROUTE_REPLAY_REPORT_PATH:-verification/reports/agent_signal_source_route_replay.latest.json}"
MAX_ROUTE_REPLAY_MISMATCH_COUNT="${MAX_ROUTE_REPLAY_MISMATCH_COUNT:-0}"
MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT="${MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT:-0}"
MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT="${MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT:-0}"
MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO="${MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO:-0.95}"
WITH_AGENT_ACTION_HINT_CASES_REPORT="${WITH_AGENT_ACTION_HINT_CASES_REPORT:-1}"
AGENT_ACTION_HINT_CASES_REPORT_PATH="${AGENT_ACTION_HINT_CASES_REPORT_PATH:-verification/reports/agent_action_hint_cases.latest.json}"
AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="${AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH:-verification/reports/agent_action_hint_missing_cases.latest.json}"
REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-1}"
AGENT_READYZ_BASE_URL="${AGENT_READYZ_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
echo "[nightly] MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
echo "[nightly] MAX_AGENT_READYZ_LEVEL=$MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REQUIRE_AGENT_READYZ_REPORT"
echo "[nightly] MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
echo "[nightly] MAX_PIPELINE_MODE_UNKNOWN_COUNT=$MAX_PIPELINE_MODE_UNKNOWN_COUNT MAX_PIPELINE_MODE_MISSING_COUNT=$MAX_PIPELINE_MODE_MISSING_COUNT"
echo "[nightly] MAX_EVENT_TYPE_MATCH_MISSING_COUNT=$MAX_EVENT_TYPE_MATCH_MISSING_COUNT MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT=$MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT MIN_EVENT_TYPE_MATCH_ALIAS_RATIO=$MIN_EVENT_TYPE_MATCH_ALIAS_RATIO"
echo "[nightly] WITH_AGENT_DECISION_AGENT_KEY_REPORT=$WITH_AGENT_DECISION_AGENT_KEY_REPORT AGENT_DECISION_AGENT_KEY_REPORT_PATH=$AGENT_DECISION_AGENT_KEY_REPORT_PATH MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT=$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT"
echo "[nightly] WITH_AGENT_ROUTE_REPLAY_REPORT=$WITH_AGENT_ROUTE_REPLAY_REPORT AGENT_ROUTE_REPLAY_REPORT_PATH=$AGENT_ROUTE_REPLAY_REPORT_PATH MAX_ROUTE_REPLAY_MISMATCH_COUNT=$MAX_ROUTE_REPLAY_MISMATCH_COUNT"
echo "[nightly] MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT=$MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT=$MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO=$MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO"
echo "[nightly] WITH_AGENT_ACTION_HINT_CASES_REPORT=$WITH_AGENT_ACTION_HINT_CASES_REPORT AGENT_ACTION_HINT_CASES_REPORT_PATH=$AGENT_ACTION_HINT_CASES_REPORT_PATH AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH=$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH"
if [[ "$WITH_AGENT_ROUTE_REPLAY_REPORT" == "1" ]]; then
  bash tools/local/run_agent_signal_source_route_replay.sh \
    --format json \
    --strict 0 \
    --output "$AGENT_ROUTE_REPLAY_REPORT_PATH" >/dev/null
  echo "[nightly] route_replay_report_path=$AGENT_ROUTE_REPLAY_REPORT_PATH"
fi
NIGHTLY_ARGS=(
  --with-pipeline-mode-report
  --with-event-type-match-report
  --with-agent-action-hint-semantics-report
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
  --max-decision-agent-key-unknown-count "$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT"
  --max-route-replay-mismatch-count "$MAX_ROUTE_REPLAY_MISMATCH_COUNT"
  --max-action-hint-semantics-mismatch-count "$MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT"
  --max-action-hint-semantics-missing-actual-hint-count "$MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT"
  --min-action-hint-semantics-match-ratio "$MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO"
)
if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
  NIGHTLY_ARGS+=(--require-agent-readyz-report)
fi
bash tools/local/aggregate_and_check.sh "${NIGHTLY_ARGS[@]}"
bash tools/local/print_pipeline_mode_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_event_type_match_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_decision_agent_key_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_route_replay_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_action_hint_semantics_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
if [[ "$WITH_AGENT_DECISION_AGENT_KEY_REPORT" == "1" ]]; then
  bash tools/local/run_agent_decision_agent_key_report.sh \
    --output "$AGENT_DECISION_AGENT_KEY_REPORT_PATH" >/dev/null
  echo "[nightly] decision_agent_key_report_path=$AGENT_DECISION_AGENT_KEY_REPORT_PATH"
  bash tools/local/check_agent_decision_agent_key_report_guard.sh \
    "$AGENT_DECISION_AGENT_KEY_REPORT_PATH" \
    "$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT"
fi
if [[ "$WITH_AGENT_ACTION_HINT_CASES_REPORT" == "1" ]]; then
  bash tools/local/inspect_agent_action_hint_cases.sh \
    --status mismatch \
    --format json \
    --output "$AGENT_ACTION_HINT_CASES_REPORT_PATH" >/dev/null
  echo "[nightly] action_hint_cases_report_path=$AGENT_ACTION_HINT_CASES_REPORT_PATH"
  bash tools/local/check_agent_action_hint_cases_guard.sh \
    "$AGENT_ACTION_HINT_CASES_REPORT_PATH" \
    "$MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT" \
    mismatch
  bash tools/local/inspect_agent_action_hint_cases.sh \
    --status missing \
    --format json \
    --output "$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" >/dev/null
  echo "[nightly] action_hint_missing_cases_report_path=$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH"
  bash tools/local/check_agent_action_hint_cases_guard.sh \
    "$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" \
    "$MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT" \
    missing
fi
