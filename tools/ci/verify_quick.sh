#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_quick.sh

Description:
  CI quick 验证入口。执行结构守卫、docs/contracts 聚合守卫（含 pipeline semantic terms doc guard）、链路 quick suite 与语义审计后处理。

Environment Switches (local debug only):
  VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1
  VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1

Optional Observability:
  WITH_AGENT_READYZ=1            启用 agent readyz 聚合观测（默认关闭）
  WITH_PIPELINE_MODE_REPORT=1    启用 pipeline_mode 灰度聚合观测（默认关闭）
  WITH_AGENT_CLOSED_LOOP_SMOKE=1 启用 agent->execution 三态闭环自检（默认关闭）
  WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1
                                启用 minimal 语义映射聚合观测（默认关闭）
  WITH_AGENT_ACTION_HINT_CASES_REPORT=1
                                生成 action_hint mismatch 回放 artifact（默认关闭）
  AGENT_ACTION_HINT_CASES_REPORT_PATH
                                action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH
                                action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
  MAX_AGENT_READYZ_LEVEL         readyz 最大允许级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS
                                decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT
                                pipeline_mode unknown 计数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_MISSING_COUNT
                                pipeline_mode 缺失计数上限（默认 -1 忽略）
  REQUIRE_AGENT_READYZ_REPORT    是否要求 readyz 报告存在（1/0，默认 0）
  AGENT_READYZ_BASE_URL          agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S         agent readyz 拉取超时秒数（默认 2.0）

CI Hard Constraints:
  当 CI=true 或 GITHUB_ACTIONS=true 时，禁止启用上述 skip 开关；若启用会直接失败（exit 2）。

Failure Codes:
  exit 1  任一守卫/测试失败
  exit 2  CI 环境下启用了禁止的 skip 开关
USAGE
  exit 0
fi

if (($# > 0)); then
  echo "[failed] unsupported args: $*"
  echo "hint: run 'bash tools/ci/verify_quick.sh --help'"
  exit 1
fi

SUMMARY_PATH="verification/reports/summary.latest.json"

# CI 强约束：禁止在 CI 环境通过 skip 开关绕过关键守卫。
if [[ "${CI:-}" == "true" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
  if [[ "${VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT:-0}" == "1" ]]; then
    echo "[failed] VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1 is not allowed in CI"
    exit 2
  fi
  if [[ "${VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL:-0}" == "1" ]]; then
    echo "[failed] VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1 is not allowed in CI"
    exit 2
  fi
fi

bash tools/local/check_structure.sh
bash tools/local/check_script_compat_whitelist.sh
if ! bash tools/local/check_docs_contracts_bundle.sh; then
  echo "[hint] docs/contracts bundle 失败，建议执行："
  echo "       bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions"
  echo "[hint] 自动输出版本探测值（用于 CI 日志/artifact 排障）："
  bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions || true
  exit 1
fi
# 显式执行来源语义守卫，保证 quick 日志可直接展示该门禁状态。
# 说明：docs/contracts bundle 内也会执行同一守卫，这里属于“可见性优先”的有意重复。
bash tools/local/check_source_semantics_guard.sh
bash tools/local/check_alternative_source_single_source_guard.sh
bash tools/local/check_feature_docs_source_names_guard.sh
if [[ "${VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT:-0}" == "1" ]]; then
  echo "[warn] skip release baseline alignment guard by VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1"
else
  bash tools/local/check_release_baseline_alignment.sh
fi
bash tools/local/check_prod_provider_modes_guard.sh
bash tools/ci/verify_all.sh --quick
# 关键负向链路冒烟：锁定 alternative source 非法 provider_state 的
# state -> agent warning -> alert_code 三段映射，防止静默语义漂移。
if test -x ./venv/bin/pytest; then
  ./venv/bin/pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
else
  python3 -m pytest -q \
    verification/validators/execution_service/test_agent_to_execution_smoke.py::test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code
fi
bash tools/local/sync_contract_indexes.sh
bash tools/local/audit_semantics.sh
if [[ "${VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL:-0}" == "1" ]]; then
  echo "[warn] skip semantic critical warning guard by VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1"
else
  bash tools/local/check_semantic_critical_warning_guard.sh
fi
if [[ "${WITH_AGENT_CLOSED_LOOP_SMOKE:-0}" == "1" ]]; then
  bash tools/local/check_agent_execution_closed_loop_smoke.sh
fi
if [[ "${WITH_AGENT_ACTION_HINT_CASES_REPORT:-0}" == "1" ]]; then
  AGENT_ACTION_HINT_CASES_REPORT_PATH="${AGENT_ACTION_HINT_CASES_REPORT_PATH:-verification/reports/agent_action_hint_cases.latest.json}"
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="${AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH:-verification/reports/agent_action_hint_missing_cases.latest.json}"
  bash tools/local/inspect_agent_action_hint_cases.sh \
    --status mismatch \
    --format json \
    --output "$AGENT_ACTION_HINT_CASES_REPORT_PATH" >/dev/null
  bash tools/local/inspect_agent_action_hint_cases.sh \
    --status missing \
    --format json \
    --output "$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" >/dev/null
  echo "[quick] action_hint_cases_report_path=$AGENT_ACTION_HINT_CASES_REPORT_PATH"
  echo "[quick] action_hint_missing_cases_report_path=$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH"
fi

if [[ "${WITH_AGENT_READYZ:-0}" == "1" || "${WITH_PIPELINE_MODE_REPORT:-0}" == "1" || "${WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT:-0}" == "1" ]]; then
  MAX_AGENT_READYZ_LEVEL="${MAX_AGENT_READYZ_LEVEL:-red}"
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:--1}"
  MAX_PIPELINE_MODE_UNKNOWN_COUNT="${MAX_PIPELINE_MODE_UNKNOWN_COUNT:--1}"
  MAX_PIPELINE_MODE_MISSING_COUNT="${MAX_PIPELINE_MODE_MISSING_COUNT:--1}"
  REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-0}"
  AGENT_READYZ_BASE_URL="${AGENT_READYZ_BASE_URL:-http://127.0.0.1:9971}"
  AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
  echo "[quick] WITH_AGENT_READYZ=${WITH_AGENT_READYZ:-0} WITH_PIPELINE_MODE_REPORT=${WITH_PIPELINE_MODE_REPORT:-0} WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=${WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT:-0} MAX_AGENT_READYZ_LEVEL=$MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REQUIRE_AGENT_READYZ_REPORT"
  echo "[quick] MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
  echo "[quick] MAX_PIPELINE_MODE_UNKNOWN_COUNT=$MAX_PIPELINE_MODE_UNKNOWN_COUNT MAX_PIPELINE_MODE_MISSING_COUNT=$MAX_PIPELINE_MODE_MISSING_COUNT"
  QUICK_ARGS=(
    --max-agent-readyz-level "$MAX_AGENT_READYZ_LEVEL"
    --max-decision-trace-schema-guard-invalid-records "$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
    --max-pipeline-mode-unknown-count "$MAX_PIPELINE_MODE_UNKNOWN_COUNT"
    --max-pipeline-mode-missing-count "$MAX_PIPELINE_MODE_MISSING_COUNT"
  )
  if [[ "${WITH_AGENT_READYZ:-0}" == "1" ]]; then
    QUICK_ARGS+=(
      --with-agent-readyz
      --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
      --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
    )
  fi
  if [[ "${WITH_PIPELINE_MODE_REPORT:-0}" == "1" ]]; then
    QUICK_ARGS+=(--with-pipeline-mode-report)
  fi
  if [[ "${WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT:-0}" == "1" ]]; then
    QUICK_ARGS+=(--with-agent-action-hint-semantics-report)
  fi
  if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
    QUICK_ARGS+=(--require-agent-readyz-report)
  fi
  QUICK_ARGS+=(--summary-path "$SUMMARY_PATH")
  bash tools/local/aggregate_and_check.sh "${QUICK_ARGS[@]}"
  bash tools/local/print_pipeline_mode_summary.sh --summary "$SUMMARY_PATH" --prefix quick
  if [[ "${WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT:-0}" == "1" ]]; then
    bash tools/local/print_action_hint_semantics_summary.sh --summary "$SUMMARY_PATH" --prefix quick
  fi
fi
