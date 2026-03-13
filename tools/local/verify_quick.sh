#!/usr/bin/env bash
set -euo pipefail

WITH_VERIFICATION_API_SCHEMA_CHECK=0
SKIP_SEMANTIC_CRITICAL_WARNING_GUARD=0
SKIP_RELEASE_BASELINE_ALIGNMENT=0
WITH_AGENT_READYZ=0
WITH_PIPELINE_MODE_REPORT=0
WITH_AGENT_CLOSED_LOOP_SMOKE=0
WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=0
WITH_AGENT_ACTION_HINT_CASES_REPORT=0
WITH_AGENT_DECISION_AGENT_KEY_REPORT=0
AGENT_ACTION_HINT_CASES_REPORT_PATH="verification/reports/agent_action_hint_cases.latest.json"
AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="verification/reports/agent_action_hint_missing_cases.latest.json"
AGENT_DECISION_AGENT_KEY_REPORT_PATH="verification/reports/agent_decision_agent_key.latest.json"
MAX_AGENT_READYZ_LEVEL="red"
MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="-1"
REQUIRE_AGENT_READYZ_REPORT=0
AGENT_READYZ_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
SHOW_HELP=0
PASS_ARGS=()

while (($# > 0)); do
  case "$1" in
    --help|-h)
      SHOW_HELP=1
      shift
      ;;
    --with-verification-api-schema-check)
      WITH_VERIFICATION_API_SCHEMA_CHECK=1
      shift
      ;;
    --skip-semantic-critical-warning-guard)
      SKIP_SEMANTIC_CRITICAL_WARNING_GUARD=1
      shift
      ;;
    --skip-release-baseline-alignment)
      SKIP_RELEASE_BASELINE_ALIGNMENT=1
      shift
      ;;
    --with-agent-readyz)
      WITH_AGENT_READYZ=1
      shift
      ;;
    --with-pipeline-mode-report)
      WITH_PIPELINE_MODE_REPORT=1
      shift
      ;;
    --with-agent-closed-loop-smoke)
      WITH_AGENT_CLOSED_LOOP_SMOKE=1
      shift
      ;;
    --with-agent-action-hint-semantics-report)
      WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1
      shift
      ;;
    --with-agent-action-hint-cases-report)
      WITH_AGENT_ACTION_HINT_CASES_REPORT=1
      shift
      ;;
    --with-agent-decision-agent-key-report)
      WITH_AGENT_DECISION_AGENT_KEY_REPORT=1
      shift
      ;;
    --agent-action-hint-cases-report-path)
      AGENT_ACTION_HINT_CASES_REPORT_PATH="${2:-$AGENT_ACTION_HINT_CASES_REPORT_PATH}"
      shift 2
      ;;
    --agent-action-hint-missing-cases-report-path)
      AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="${2:-$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH}"
      shift 2
      ;;
    --agent-decision-agent-key-report-path)
      AGENT_DECISION_AGENT_KEY_REPORT_PATH="${2:-$AGENT_DECISION_AGENT_KEY_REPORT_PATH}"
      shift 2
      ;;
    --max-agent-readyz-level)
      MAX_AGENT_READYZ_LEVEL="${2:-$MAX_AGENT_READYZ_LEVEL}"
      shift 2
      ;;
    --max-decision-agent-key-unknown-count)
      MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="${2:-$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT}"
      shift 2
      ;;
    --require-agent-readyz-report)
      REQUIRE_AGENT_READYZ_REPORT=1
      shift
      ;;
    --agent-readyz-base-url)
      AGENT_READYZ_BASE_URL="${2:-$AGENT_READYZ_BASE_URL}"
      shift 2
      ;;
    --agent-readyz-timeout-s)
      AGENT_READYZ_TIMEOUT_S="${2:-$AGENT_READYZ_TIMEOUT_S}"
      shift 2
      ;;
    *)
      PASS_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$SHOW_HELP" == "1" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/local/verify_quick.sh [options] [args...]

Description:
  本地 quick 验证入口，代理到：
    bash tools/ci/verify_quick.sh [args...]
  说明：继承 CI quick 全量门禁，包含 pipeline semantic terms doc guard。

Options:
  --with-verification-api-schema-check   追加执行 verification API summary schema 开关校验测试
  --skip-semantic-critical-warning-guard 跳过 semantic critical warning guard（仅本地调试）
  --skip-release-baseline-alignment      跳过 release baseline 对齐校验（仅本地调试）
  --with-agent-readyz                    启用 agent readyz 聚合观测（默认关闭）
  --with-pipeline-mode-report            启用 pipeline_mode 灰度聚合观测（默认关闭）
  --with-agent-closed-loop-smoke         启用 agent->execution 三态闭环自检（默认关闭）
  --with-agent-action-hint-semantics-report
                                          启用 minimal 语义映射聚合观测（默认关闭）
  --with-agent-action-hint-cases-report   生成 action_hint mismatch 回放 artifact（默认关闭）
  --with-agent-decision-agent-key-report  启用 decision_agent_key 路由分布观测（默认关闭）
  --agent-action-hint-cases-report-path <path>
                                          指定 action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  --agent-action-hint-missing-cases-report-path <path>
                                          指定 action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
  --agent-decision-agent-key-report-path <path>
                                          指定 decision_agent_key 报告输出路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  --max-agent-readyz-level <level>       设置 readyz 最大允许级别（默认 red）
  --max-decision-agent-key-unknown-count <int>
                                          设置 decision_agent_key unknown 计数上限（默认 -1 忽略）
  --require-agent-readyz-report          要求存在 readyz 报告（默认关闭）
  --agent-readyz-base-url <url>          指定 readyz 地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec>         指定 readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
USAGE
  exit 0
fi

ENV_PREFIX=()
if [[ "$SKIP_SEMANTIC_CRITICAL_WARNING_GUARD" == "1" ]]; then
  ENV_PREFIX+=(VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1)
fi
if [[ "$SKIP_RELEASE_BASELINE_ALIGNMENT" == "1" ]]; then
  ENV_PREFIX+=(VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1)
fi
if [[ "$WITH_AGENT_READYZ" == "1" ]]; then
  ENV_PREFIX+=(WITH_AGENT_READYZ=1)
fi
if [[ "$WITH_PIPELINE_MODE_REPORT" == "1" ]]; then
  ENV_PREFIX+=(WITH_PIPELINE_MODE_REPORT=1)
fi
if [[ "$WITH_AGENT_CLOSED_LOOP_SMOKE" == "1" ]]; then
  ENV_PREFIX+=(WITH_AGENT_CLOSED_LOOP_SMOKE=1)
fi
if [[ "$WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT" == "1" ]]; then
  ENV_PREFIX+=(WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1)
fi
if [[ "$WITH_AGENT_ACTION_HINT_CASES_REPORT" == "1" ]]; then
  ENV_PREFIX+=(WITH_AGENT_ACTION_HINT_CASES_REPORT=1)
  ENV_PREFIX+=(AGENT_ACTION_HINT_CASES_REPORT_PATH="$AGENT_ACTION_HINT_CASES_REPORT_PATH")
  ENV_PREFIX+=(AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH")
fi
if [[ "$WITH_AGENT_DECISION_AGENT_KEY_REPORT" == "1" ]]; then
  ENV_PREFIX+=(WITH_AGENT_DECISION_AGENT_KEY_REPORT=1)
  ENV_PREFIX+=(AGENT_DECISION_AGENT_KEY_REPORT_PATH="$AGENT_DECISION_AGENT_KEY_REPORT_PATH")
fi
ENV_PREFIX+=(MAX_AGENT_READYZ_LEVEL="$MAX_AGENT_READYZ_LEVEL")
ENV_PREFIX+=(MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT")
ENV_PREFIX+=(REQUIRE_AGENT_READYZ_REPORT="$REQUIRE_AGENT_READYZ_REPORT")
ENV_PREFIX+=(AGENT_READYZ_BASE_URL="$AGENT_READYZ_BASE_URL")
ENV_PREFIX+=(AGENT_READYZ_TIMEOUT_S="$AGENT_READYZ_TIMEOUT_S")
CMD=(bash tools/ci/verify_quick.sh)
if ((${#PASS_ARGS[@]} > 0)); then
  CMD+=("${PASS_ARGS[@]}")
fi
if ((${#ENV_PREFIX[@]} > 0)); then
  env "${ENV_PREFIX[@]}" "${CMD[@]}"
else
  "${CMD[@]}"
fi

if [[ "$WITH_VERIFICATION_API_SCHEMA_CHECK" == "1" ]]; then
  if test -x ./venv/bin/pytest; then
    ./venv/bin/pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  else
    python3 -m pytest -q \
      verification/text/test_verification_api.py::test_verification_api_summary_schema_validation_enabled_passes
  fi
fi
