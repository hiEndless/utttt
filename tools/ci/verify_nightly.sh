#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/ci/verify_nightly.sh

Description:
  CI nightly 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、全量报告回归链路与语义聚合校验。

Environment:
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
  MAX_DECISION_AGENT_KEY_GENERIC_RATIO  decision_agent_key generic 占比上限（默认 0.40）
  WITH_AGENT_ROUTE_REPLAY_REPORT  是否生成四类来源业务路由回放 artifact（1/0，默认 1）
  AGENT_ROUTE_REPLAY_REPORT_PATH  route replay 报告路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  MAX_ROUTE_REPLAY_MISMATCH_COUNT  route_replay mismatch 计数上限（默认 0）
  WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY  是否执行 signal_router 基线路由回放（1/0，默认 1）
  AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH  baseline 样本路径（默认 services/agent_server_new/config/signal_router_baseline_samples.json）
  AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH  baseline replay 报告路径（默认 verification/reports/agent_signal_router_baseline_replay.latest.json）
  AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT  baseline replay 是否严格失败（1/0，默认 0）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT  是否生成信号决策回放 artifact（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH  signal decision replay 报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT  signal decision replay 每来源最小样本数（默认 10）
  MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO  market_indicator 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO  onchain_wallet 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO  large_liquidation 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO  social_news 的 rule_fallback 比例上限（默认 0.90）
  MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT  signal decision source quality 每来源最小样本数（默认 10）
  MIN_MARKET_INDICATOR_LLM_OK_RATIO  market_indicator 的 llm_ok 比例下限（默认 -1 忽略）
  MIN_ONCHAIN_WALLET_LLM_OK_RATIO  onchain_wallet 的 llm_ok 比例下限（默认 -1 忽略）
  MIN_LARGE_LIQUIDATION_LLM_OK_RATIO  large_liquidation 的 llm_ok 比例下限（默认 -1 忽略）
  MIN_SOCIAL_NEWS_LLM_OK_RATIO  social_news 的 llm_ok 比例下限（默认 -1 忽略）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND  是否输出 signal decision replay 趋势摘要（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB  趋势输入 glob（默认 verification/reports/agent_signal_decision_replay*.json）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS  趋势窗口天数（默认 7）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE  趋势来源类型（默认 social_news）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH  趋势报告输出路径（默认 verification/reports/agent_signal_decision_replay_trend.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO  趋势建议触发阈值（默认 0.70）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS  趋势建议连续天数下限（默认 3）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL  趋势建议总样本数下限（默认 20）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH  趋势建议输出路径（默认 verification/reports/agent_signal_decision_replay_recommendation.latest.json）
  MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT  action_hint_semantics mismatch 计数上限（默认 0）
  MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT  action_hint_semantics missing_actual_hint 计数上限（默认 0）
  MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO  action_hint_semantics match_ratio 下限（默认 0.95）
  MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT  signal_decision_llm_observe missing_decision_mode 计数上限（默认 0）
  MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT  signal_decision_llm_observe missing_llm_parse_status 计数上限（默认 0）
  MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT  signal_decision_llm_observe decision_mode_llm_count 下限（默认 -1 忽略）
  MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT  signal_decision_llm_observe llm_parse_status_llm_ok_count 下限（默认 -1 忽略）
  WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT  是否输出 llm_observe trend recommendation 发布提示（1/0，默认 1）
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
MAX_DECISION_AGENT_KEY_GENERIC_RATIO="${MAX_DECISION_AGENT_KEY_GENERIC_RATIO:-0.40}"
WITH_AGENT_ROUTE_REPLAY_REPORT="${WITH_AGENT_ROUTE_REPLAY_REPORT:-1}"
AGENT_ROUTE_REPLAY_REPORT_PATH="${AGENT_ROUTE_REPLAY_REPORT_PATH:-verification/reports/agent_signal_source_route_replay.latest.json}"
MAX_ROUTE_REPLAY_MISMATCH_COUNT="${MAX_ROUTE_REPLAY_MISMATCH_COUNT:-0}"
WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY="${WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY:-1}"
AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH="${AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH:-services/agent_server_new/config/signal_router_baseline_samples.json}"
AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH="${AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH:-verification/reports/agent_signal_router_baseline_replay.latest.json}"
AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT="${AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT:-0}"
WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT="${WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT:-1}"
AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH="${AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH:-verification/reports/agent_signal_decision_replay.latest.json}"
AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT="${AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT:-10}"
MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO="${MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO:--1}"
MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO="${MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO:--1}"
MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO="${MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO:--1}"
MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO="${MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO:-0.90}"
MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT="${MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT:-10}"
MIN_MARKET_INDICATOR_LLM_OK_RATIO="${MIN_MARKET_INDICATOR_LLM_OK_RATIO:--1}"
MIN_ONCHAIN_WALLET_LLM_OK_RATIO="${MIN_ONCHAIN_WALLET_LLM_OK_RATIO:--1}"
MIN_LARGE_LIQUIDATION_LLM_OK_RATIO="${MIN_LARGE_LIQUIDATION_LLM_OK_RATIO:--1}"
MIN_SOCIAL_NEWS_LLM_OK_RATIO="${MIN_SOCIAL_NEWS_LLM_OK_RATIO:--1}"
WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND="${WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND:-1}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB="${AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB:-verification/reports/agent_signal_decision_replay*.json}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS="${AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS:-7}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE="${AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE:-social_news}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH="${AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH:-verification/reports/agent_signal_decision_replay_trend.latest.json}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO="${AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO:-0.70}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS="${AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS:-3}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL="${AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL:-20}"
AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH="${AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH:-verification/reports/agent_signal_decision_replay_recommendation.latest.json}"
MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT="${MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT:-0}"
MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT="${MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT:-0}"
MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO="${MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO:-0.95}"
MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT="${MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT:-0}"
MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT="${MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT:-0}"
MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT="${MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT:--1}"
MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT="${MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT:--1}"
WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT="${WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT:-1}"
WITH_AGENT_ACTION_HINT_CASES_REPORT="${WITH_AGENT_ACTION_HINT_CASES_REPORT:-1}"
AGENT_ACTION_HINT_CASES_REPORT_PATH="${AGENT_ACTION_HINT_CASES_REPORT_PATH:-verification/reports/agent_action_hint_cases.latest.json}"
AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH="${AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH:-verification/reports/agent_action_hint_missing_cases.latest.json}"
AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH="${AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH:-verification/reports/agent_signal_decision_llm_observe.latest.json}"
AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_REPORT_PATH="${AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_REPORT_PATH:-verification/reports/agent_signal_decision_llm_observe_agent_key_trend.latest.json}"
AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH="${AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH:-verification/reports/agent_signal_decision_llm_observe_agent_key_trend_recommendation.latest.json}"
REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-1}"
AGENT_READYZ_BASE_URL="${AGENT_READYZ_BASE_URL:-http://127.0.0.1:9971}"
AGENT_READYZ_TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"
echo "[nightly] MAX_AGENT_READYZ_LEVEL=$MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REQUIRE_AGENT_READYZ_REPORT"
echo "[nightly] MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
echo "[nightly] MAX_PIPELINE_MODE_UNKNOWN_COUNT=$MAX_PIPELINE_MODE_UNKNOWN_COUNT MAX_PIPELINE_MODE_MISSING_COUNT=$MAX_PIPELINE_MODE_MISSING_COUNT"
echo "[nightly] MAX_EVENT_TYPE_MATCH_MISSING_COUNT=$MAX_EVENT_TYPE_MATCH_MISSING_COUNT MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT=$MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT MIN_EVENT_TYPE_MATCH_ALIAS_RATIO=$MIN_EVENT_TYPE_MATCH_ALIAS_RATIO"
echo "[nightly] WITH_AGENT_DECISION_AGENT_KEY_REPORT=$WITH_AGENT_DECISION_AGENT_KEY_REPORT AGENT_DECISION_AGENT_KEY_REPORT_PATH=$AGENT_DECISION_AGENT_KEY_REPORT_PATH MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT=$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT MAX_DECISION_AGENT_KEY_GENERIC_RATIO=$MAX_DECISION_AGENT_KEY_GENERIC_RATIO"
echo "[nightly] WITH_AGENT_ROUTE_REPLAY_REPORT=$WITH_AGENT_ROUTE_REPLAY_REPORT AGENT_ROUTE_REPLAY_REPORT_PATH=$AGENT_ROUTE_REPLAY_REPORT_PATH MAX_ROUTE_REPLAY_MISMATCH_COUNT=$MAX_ROUTE_REPLAY_MISMATCH_COUNT"
echo "[nightly] WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY=$WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH=$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH=$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT=$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT"
echo "[nightly] WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT=$WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH=$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT=$AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT"
echo "[nightly] MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO=$MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO=$MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO=$MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO=$MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO"
echo "[nightly] MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT=$MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT MIN_MARKET_INDICATOR_LLM_OK_RATIO=$MIN_MARKET_INDICATOR_LLM_OK_RATIO MIN_ONCHAIN_WALLET_LLM_OK_RATIO=$MIN_ONCHAIN_WALLET_LLM_OK_RATIO MIN_LARGE_LIQUIDATION_LLM_OK_RATIO=$MIN_LARGE_LIQUIDATION_LLM_OK_RATIO MIN_SOCIAL_NEWS_LLM_OK_RATIO=$MIN_SOCIAL_NEWS_LLM_OK_RATIO"
echo "[nightly] WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND=$WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB=$AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS=$AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE=$AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH=$AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH"
echo "[nightly] AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO=$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS=$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL=$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL"
echo "[nightly] AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH=$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH"
echo "[nightly] MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT=$MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT=$MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO=$MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO"
echo "[nightly] MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT=$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT=$MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT=$MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT=$MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT"
echo "[nightly] WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT=$WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT"
echo "[nightly] WITH_AGENT_ACTION_HINT_CASES_REPORT=$WITH_AGENT_ACTION_HINT_CASES_REPORT AGENT_ACTION_HINT_CASES_REPORT_PATH=$AGENT_ACTION_HINT_CASES_REPORT_PATH AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH=$AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH"
echo "[nightly] AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH"
echo "[nightly] AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_REPORT_PATH=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_REPORT_PATH"
echo "[nightly] AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH"
if bash tools/local/run_agent_signal_decision_llm_observe_report.sh \
  --output "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH" >/dev/null; then
  echo "[nightly] signal_decision_llm_observe_report_path=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH"
  bash tools/local/print_signal_decision_llm_observe_summary.sh \
    --report "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH" \
    --prefix nightly
  bash tools/local/print_signal_decision_llm_observe_agent_key_coverage.sh \
    --report "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH" \
    --prefix nightly
  bash tools/local/print_signal_decision_llm_observe_agent_key_trend.sh \
    --glob "verification/reports/agent_signal_decision_llm_observe*.json" \
    --days 7 \
    --min-ratio 0.15 \
    --min-consecutive-days 3 \
    --agent-keys "social_news,onchain,technical,liquidation" \
    --output "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_REPORT_PATH" \
    --recommendation-output "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH" \
    --prefix nightly
  LLM_OBSERVE_TREND_RECOMMENDATION_STATUS="$(python3 - <<'PY' "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    print("missing")
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print("invalid_json")
    raise SystemExit(0)
if str(payload.get("schema_version") or "") != "agent-signal-decision-llm-observe-agent-key-trend-recommendation-v1":
    print("unsupported_schema_version")
    raise SystemExit(0)
status = str(payload.get("status") or "").strip().lower()
if status in {"recommend", "hold", "skip"}:
    print(status)
else:
    print("unknown_status")
PY
)"
  echo "[nightly] llm_observe_trend_recommendation_status=$LLM_OBSERVE_TREND_RECOMMENDATION_STATUS recommendation_report_path=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH"
  if [[ "$WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT" == "1" ]]; then
    bash tools/local/print_signal_decision_llm_observe_trend_recommendation_hint.sh \
      "$AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_REPORT_PATH"
  fi
else
  echo "[nightly] signal_decision_llm_observe_report_failed path=$AGENT_SIGNAL_DECISION_LLM_OBSERVE_REPORT_PATH"
fi
if [[ "$WITH_AGENT_ROUTE_REPLAY_REPORT" == "1" ]]; then
  bash tools/local/run_agent_signal_source_route_replay.sh \
    --format json \
    --strict 0 \
    --output "$AGENT_ROUTE_REPLAY_REPORT_PATH" >/dev/null
  echo "[nightly] route_replay_report_path=$AGENT_ROUTE_REPLAY_REPORT_PATH"
fi
if [[ "$WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY" == "1" ]]; then
  bash tools/local/run_agent_signal_router_baseline_replay.sh \
    --samples "$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH" \
    --format json \
    --output "$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH" \
    --strict "$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT" >/dev/null
  echo "[nightly] signal_router_baseline_replay_report_path=$AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH"
fi
if [[ "$WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT" == "1" ]]; then
  bash tools/local/run_agent_signal_decision_replay_report.sh \
    --output "$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" >/dev/null
  echo "[nightly] signal_decision_replay_report_path=$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH"
  bash tools/local/print_signal_decision_quality_summary.sh \
    --report "$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" \
    --prefix nightly
  bash tools/local/check_agent_signal_decision_replay_guard.sh \
    "$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" \
    "$AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT" \
    "$MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO" \
    "$MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO" \
    "$MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO" \
    "$MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO"
  bash tools/local/check_agent_signal_decision_source_quality_guard.sh \
    "$AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" \
    "$MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT" \
    "$MIN_MARKET_INDICATOR_LLM_OK_RATIO" \
    "$MIN_ONCHAIN_WALLET_LLM_OK_RATIO" \
    "$MIN_LARGE_LIQUIDATION_LLM_OK_RATIO" \
    "$MIN_SOCIAL_NEWS_LLM_OK_RATIO"
  if [[ "$WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND" == "1" ]]; then
    bash tools/local/print_agent_signal_decision_replay_trend.sh \
      --glob "$AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB" \
      --source "$AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE" \
      --days "$AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS" \
      --output "$AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH" \
      --prefix nightly
    bash tools/local/check_agent_signal_decision_replay_trend_recommendation.sh \
      "$AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH" \
      "$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO" \
      "$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS" \
      "$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL" \
      "$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH"
  fi
fi
RECOMMENDATION_ARTIFACT_STATUS="$(bash tools/local/read_agent_signal_decision_recommendation_status.sh "$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH")"
echo "[nightly] recommendation_artifact_status=$RECOMMENDATION_ARTIFACT_STATUS recommendation_report_path=$AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH"
NIGHTLY_ARGS=(
  --with-pipeline-mode-report
  --with-event-type-match-report
  --with-agent-action-hint-semantics-report
  --with-signal-decision-llm-observe-report
  --with-agent-readyz
  --summary-path "$SUMMARY_PATH"
  --agent-readyz-base-url "$AGENT_READYZ_BASE_URL"
  --agent-readyz-timeout-s "$AGENT_READYZ_TIMEOUT_S"
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
  NIGHTLY_ARGS+=(--require-agent-readyz-report)
fi
bash tools/local/aggregate_and_check.sh "${NIGHTLY_ARGS[@]}"
bash tools/local/print_pipeline_mode_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_event_type_match_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_decision_agent_key_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_route_replay_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_action_hint_semantics_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
bash tools/local/print_signal_decision_llm_observe_aggregate_summary.sh --summary "$SUMMARY_PATH" --prefix nightly
if [[ "$WITH_AGENT_DECISION_AGENT_KEY_REPORT" == "1" ]]; then
  bash tools/local/run_agent_decision_agent_key_report.sh \
    --output "$AGENT_DECISION_AGENT_KEY_REPORT_PATH" >/dev/null
  echo "[nightly] decision_agent_key_report_path=$AGENT_DECISION_AGENT_KEY_REPORT_PATH"
  bash tools/local/check_agent_decision_agent_key_report_guard.sh \
    "$AGENT_DECISION_AGENT_KEY_REPORT_PATH" \
    "$MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT" \
    "$MAX_DECISION_AGENT_KEY_GENERIC_RATIO"
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
