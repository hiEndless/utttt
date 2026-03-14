#!/usr/bin/env bash
set -euo pipefail

SUMMARY_PATH="verification/reports/summary.latest.json"
MEMORY_SUMMARY_PATH="verification/reports/memory_summary.latest.json"
AGENT_READYZ_PATH="verification/reports/agent_readyz.latest.json"
DECISION_TRACE_SCHEMA_GUARD_PATH="verification/reports/agent_decision_trace_schema_guard.latest.json"
PIPELINE_MODE_REPORT_PATH="verification/reports/agent_pipeline_mode.latest.json"
EXECUTION_PROMPT_REPORT_PATH="verification/reports/execution_prompt_version.latest.json"
EVENT_TYPE_MATCH_REPORT_PATH="verification/reports/agent_event_type_match.latest.json"
ACTION_HINT_SEMANTICS_REPORT_PATH="verification/reports/agent_action_hint_semantics.latest.json"
SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH="verification/reports/agent_signal_decision_llm_observe.latest.json"
AGENT_READYZ_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
WITH_MEMORY_SUMMARY=0
WITH_AGENT_READYZ=0
WITH_DECISION_TRACE_SCHEMA_GUARD=0
WITH_PIPELINE_MODE_REPORT=0
WITH_EXECUTION_PROMPT_REPORT=0
WITH_EVENT_TYPE_MATCH_REPORT=0
WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=0
WITH_SIGNAL_DECISION_LLM_OBSERVE_REPORT=0
SKIP_THRESHOLDS=0
COMPACT=0
MAX_AGENT_READYZ_LEVEL="red"
REQUIRE_AGENT_READYZ_REPORT=0
MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="-1"
MAX_PIPELINE_MODE_UNKNOWN_COUNT="-1"
MAX_PIPELINE_MODE_MISSING_COUNT="-1"
MAX_EVENT_TYPE_MATCH_MISSING_COUNT="-1"
MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT="-1"
MIN_EVENT_TYPE_MATCH_ALIAS_RATIO="-1"
MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="-1"
MAX_ROUTE_REPLAY_MISMATCH_COUNT="-1"
MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT="-1"
MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT="-1"
MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO="-1"
MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT="-1"
MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT="-1"
MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT="-1"
MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT="-1"

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/aggregate_and_check.sh [options]

Options:
  --with-memory-summary         先生成 memory summary 再聚合
  --with-agent-readyz           先生成 agent readyz 报告再聚合
  --with-decision-trace-schema-guard  先生成 decision_trace schema guard 报告再聚合
  --with-pipeline-mode-report   先生成 pipeline_mode 灰度报告再聚合
  --with-execution-prompt-report  先生成 execution prompt 版本报告再聚合
  --with-event-type-match-report  先生成 event_type 命中报告再聚合
  --with-agent-action-hint-semantics-report  先生成 action_hint 语义映射报告再聚合
  --with-signal-decision-llm-observe-report  先生成 signal decision LLM observe 报告再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --agent-readyz-path <path>    agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --decision-trace-schema-guard-path <path>
                               decision_trace schema guard 报告输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --pipeline-mode-report-path <path>
                               pipeline_mode 报告输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --execution-prompt-report-path <path>
                               execution prompt 报告输出路径（默认 verification/reports/execution_prompt_version.latest.json）
  --event-type-match-report-path <path>
                               event_type 命中报告输出路径（默认 verification/reports/agent_event_type_match.latest.json）
  --agent-action-hint-semantics-report-path <path>
                               action_hint 语义映射报告输出路径（默认 verification/reports/agent_action_hint_semantics.latest.json）
  --signal-decision-llm-observe-report-path <path>
                               signal decision LLM observe 报告输出路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
  --agent-readyz-base-url <url> agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --compact                     生成紧凑 JSON（透传给 aggregate_reports --compact）
  --skip-thresholds             仅聚合，不执行阈值检查
  --max-agent-readyz-level <green|yellow|red>
                               agent readyz 最大允许状态级别（默认 red）
  --max-decision-trace-schema-guard-invalid-records <int>
                               decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  --max-pipeline-mode-unknown-count <int>
                               pipeline_mode unknown 计数上限（默认 -1 忽略）
  --max-pipeline-mode-missing-count <int>
                               pipeline_mode 缺失计数上限（默认 -1 忽略）
  --max-event-type-match-missing-count <int>
                               event_type_match 缺失计数上限（默认 -1 忽略）
  --max-event-type-match-unknown-count <int>
                               event_type_match unknown 计数上限（默认 -1 忽略）
  --min-event-type-match-alias-ratio <float>
                               event_type_match alias 占比下限（默认 -1 忽略）
  --max-decision-agent-key-unknown-count <int>
                               decision_agent_key unknown 计数上限（默认 -1 忽略）
  --max-route-replay-mismatch-count <int>
                               route_replay mismatch 计数上限（默认 -1 忽略）
  --max-action-hint-semantics-mismatch-count <int>
                               action_hint_semantics mismatch 计数上限（默认 -1 忽略）
  --max-action-hint-semantics-missing-actual-hint-count <int>
                               action_hint_semantics missing_actual_hint 计数上限（默认 -1 忽略）
  --min-action-hint-semantics-match-ratio <float>
                               action_hint_semantics match_ratio 下限（默认 -1 忽略）
  --max-signal-decision-llm-observe-missing-decision-mode-count <int>
                               signal_decision_llm_observe missing_decision_mode 计数上限（默认 -1 忽略）
  --max-signal-decision-llm-observe-missing-llm-parse-status-count <int>
                               signal_decision_llm_observe missing_llm_parse_status 计数上限（默认 -1 忽略）
  --min-signal-decision-llm-observe-decision-mode-llm-count <int>
                               signal_decision_llm_observe decision_mode_llm_count 下限（默认 -1 忽略）
  --min-signal-decision-llm-observe-llm-parse-status-llm-ok-count <int>
                               signal_decision_llm_observe llm_parse_status_llm_ok_count 下限（默认 -1 忽略）
  --require-agent-readyz-report 要求存在 agent readyz 报告（默认关闭）
  --help, -h                    显示帮助
USAGE
      exit 0
      ;;
    --with-memory-summary)
      WITH_MEMORY_SUMMARY=1
      shift
      ;;
    --with-agent-readyz)
      WITH_AGENT_READYZ=1
      shift
      ;;
    --with-decision-trace-schema-guard)
      WITH_DECISION_TRACE_SCHEMA_GUARD=1
      shift
      ;;
    --with-pipeline-mode-report)
      WITH_PIPELINE_MODE_REPORT=1
      shift
      ;;
    --with-execution-prompt-report)
      WITH_EXECUTION_PROMPT_REPORT=1
      shift
      ;;
    --with-event-type-match-report)
      WITH_EVENT_TYPE_MATCH_REPORT=1
      shift
      ;;
    --with-agent-action-hint-semantics-report)
      WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1
      shift
      ;;
    --with-signal-decision-llm-observe-report)
      WITH_SIGNAL_DECISION_LLM_OBSERVE_REPORT=1
      shift
      ;;
    --summary-path)
      SUMMARY_PATH="${2:-$SUMMARY_PATH}"
      shift 2
      ;;
    --memory-summary-path)
      MEMORY_SUMMARY_PATH="${2:-$MEMORY_SUMMARY_PATH}"
      shift 2
      ;;
    --agent-readyz-path)
      AGENT_READYZ_PATH="${2:-$AGENT_READYZ_PATH}"
      shift 2
      ;;
    --decision-trace-schema-guard-path)
      DECISION_TRACE_SCHEMA_GUARD_PATH="${2:-$DECISION_TRACE_SCHEMA_GUARD_PATH}"
      shift 2
      ;;
    --pipeline-mode-report-path)
      PIPELINE_MODE_REPORT_PATH="${2:-$PIPELINE_MODE_REPORT_PATH}"
      shift 2
      ;;
    --execution-prompt-report-path)
      EXECUTION_PROMPT_REPORT_PATH="${2:-$EXECUTION_PROMPT_REPORT_PATH}"
      shift 2
      ;;
    --event-type-match-report-path)
      EVENT_TYPE_MATCH_REPORT_PATH="${2:-$EVENT_TYPE_MATCH_REPORT_PATH}"
      shift 2
      ;;
    --agent-action-hint-semantics-report-path)
      ACTION_HINT_SEMANTICS_REPORT_PATH="${2:-$ACTION_HINT_SEMANTICS_REPORT_PATH}"
      shift 2
      ;;
    --signal-decision-llm-observe-report-path)
      SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH="${2:-$SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH}"
      shift 2
      ;;
    --agent-readyz-base-url)
      AGENT_READYZ_BASE_URL="${2:-$AGENT_READYZ_BASE_URL}"
      shift 2
      ;;
    --agent-readyz-timeout-s)
      AGENT_READYZ_TIMEOUT_S="${2:-$AGENT_READYZ_TIMEOUT_S}"
      shift 2
      ;;
    --skip-thresholds)
      SKIP_THRESHOLDS=1
      shift
      ;;
    --compact)
      COMPACT=1
      shift
      ;;
    --max-agent-readyz-level)
      MAX_AGENT_READYZ_LEVEL="${2:-$MAX_AGENT_READYZ_LEVEL}"
      shift 2
      ;;
    --max-decision-trace-schema-guard-invalid-records)
      MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${2:-$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS}"
      shift 2
      ;;
    --max-pipeline-mode-unknown-count)
      MAX_PIPELINE_MODE_UNKNOWN_COUNT="${2:-$MAX_PIPELINE_MODE_UNKNOWN_COUNT}"
      shift 2
      ;;
    --max-pipeline-mode-missing-count)
      MAX_PIPELINE_MODE_MISSING_COUNT="${2:-$MAX_PIPELINE_MODE_MISSING_COUNT}"
      shift 2
      ;;
    --max-event-type-match-missing-count)
      MAX_EVENT_TYPE_MATCH_MISSING_COUNT="${2:-$MAX_EVENT_TYPE_MATCH_MISSING_COUNT}"
      shift 2
      ;;
    --max-event-type-match-unknown-count)
      MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT="${2:-$MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT}"
      shift 2
      ;;
    --min-event-type-match-alias-ratio)
      MIN_EVENT_TYPE_MATCH_ALIAS_RATIO="${2:-$MIN_EVENT_TYPE_MATCH_ALIAS_RATIO}"
      shift 2
      ;;
    --max-decision-agent-key-unknown-count)
      MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT="${2:-$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT}"
      shift 2
      ;;
    --max-route-replay-mismatch-count)
      MAX_ROUTE_REPLAY_MISMATCH_COUNT="${2:-$MAX_ROUTE_REPLAY_MISMATCH_COUNT}"
      shift 2
      ;;
    --max-action-hint-semantics-mismatch-count)
      MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT="${2:-$MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT}"
      shift 2
      ;;
    --max-action-hint-semantics-missing-actual-hint-count)
      MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT="${2:-$MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT}"
      shift 2
      ;;
    --min-action-hint-semantics-match-ratio)
      MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO="${2:-$MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO}"
      shift 2
      ;;
    --max-signal-decision-llm-observe-missing-decision-mode-count)
      MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT="${2:-$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT}"
      shift 2
      ;;
    --max-signal-decision-llm-observe-missing-llm-parse-status-count)
      MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT="${2:-$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT}"
      shift 2
      ;;
    --min-signal-decision-llm-observe-decision-mode-llm-count)
      MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT="${2:-$MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT}"
      shift 2
      ;;
    --min-signal-decision-llm-observe-llm-parse-status-llm-ok-count)
      MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT="${2:-$MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT}"
      shift 2
      ;;
    --require-agent-readyz-report)
      REQUIRE_AGENT_READYZ_REPORT=1
      shift
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

AGGREGATE_ARGS=(--glob 'verification/reports/*.json' --output "$SUMMARY_PATH")
if [[ "$WITH_MEMORY_SUMMARY" == "1" ]]; then
  AGGREGATE_ARGS+=(--with-memory-summary --memory-summary-path "$MEMORY_SUMMARY_PATH")
fi
if [[ "$WITH_AGENT_READYZ" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-agent-readyz
    --agent-readyz-path "$AGENT_READYZ_PATH"
    --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
    --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
  )
fi
if [[ "$WITH_DECISION_TRACE_SCHEMA_GUARD" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-decision-trace-schema-guard
    --decision-trace-schema-guard-path "$DECISION_TRACE_SCHEMA_GUARD_PATH"
  )
fi
if [[ "$WITH_PIPELINE_MODE_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-pipeline-mode-report
    --pipeline-mode-report-path "$PIPELINE_MODE_REPORT_PATH"
  )
fi
if [[ "$WITH_EXECUTION_PROMPT_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-execution-prompt-report
    --execution-prompt-report-path "$EXECUTION_PROMPT_REPORT_PATH"
  )
fi
if [[ "$WITH_EVENT_TYPE_MATCH_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-event-type-match-report
    --event-type-match-report-path "$EVENT_TYPE_MATCH_REPORT_PATH"
  )
fi
if [[ "$WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-agent-action-hint-semantics-report
    --agent-action-hint-semantics-report-path "$ACTION_HINT_SEMANTICS_REPORT_PATH"
  )
fi
if [[ "$WITH_SIGNAL_DECISION_LLM_OBSERVE_REPORT" == "1" ]]; then
  AGGREGATE_ARGS+=(
    --with-signal-decision-llm-observe-report
    --signal-decision-llm-observe-report-path "$SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH"
  )
fi
if [[ "$COMPACT" == "1" ]]; then
  AGGREGATE_ARGS+=(--compact)
fi
bash tools/local/verify_report_aggregate.sh "${AGGREGATE_ARGS[@]}"
if [[ "$SKIP_THRESHOLDS" == "0" ]]; then
  THRESHOLD_ARGS=(
    --summary "$SUMMARY_PATH"
    --min-pass-rate 1.0
    --max-failed 0
    --min-reports 1
    --max-semantic-errors 0
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
    --max-signal-decision-llm-observe-missing-decision-mode-count "$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT"
    --max-signal-decision-llm-observe-missing-llm-parse-status-count "$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT"
    --min-signal-decision-llm-observe-decision-mode-llm-count "$MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT"
    --min-signal-decision-llm-observe-llm-parse-status-llm-ok-count "$MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT"
  )
  if [[ "$REQUIRE_AGENT_READYZ_REPORT" == "1" ]]; then
    THRESHOLD_ARGS+=(--require-agent-readyz-report)
  fi
  python3 -m verification.reports.check_thresholds \
    "${THRESHOLD_ARGS[@]}"
fi
