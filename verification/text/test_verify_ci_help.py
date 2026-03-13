from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run_help(script: str) -> str:
    proc = subprocess.run(
        ["bash", script, "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    return str(proc.stdout or "")


def test_verify_regression_help_contains_pipeline_semantic_terms_guard() -> None:
    out = _run_help("tools/ci/verify_regression.sh")
    assert "Usage:" in out
    assert "pipeline semantic terms doc guard" in out
    assert "MAX_AGENT_READYZ_LEVEL" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out
    assert "MAX_PIPELINE_MODE_UNKNOWN_COUNT" in out
    assert "MAX_PIPELINE_MODE_MISSING_COUNT" in out
    assert "MAX_EVENT_TYPE_MATCH_MISSING_COUNT" in out
    assert "MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT" in out
    assert "MIN_EVENT_TYPE_MATCH_ALIAS_RATIO" in out
    assert "WITH_AGENT_DECISION_AGENT_KEY_REPORT" in out
    assert "AGENT_DECISION_AGENT_KEY_REPORT_PATH" in out
    assert "MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT" in out
    assert "MAX_DECISION_AGENT_KEY_GENERIC_RATIO" in out
    assert "WITH_AGENT_ROUTE_REPLAY_REPORT" in out
    assert "AGENT_ROUTE_REPLAY_REPORT_PATH" in out
    assert "MAX_ROUTE_REPLAY_MISMATCH_COUNT" in out
    assert "WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT" in out
    assert "MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO" in out
    assert "MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO" in out
    assert "MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO" in out
    assert "MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO" in out
    assert "MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT" in out
    assert "MIN_MARKET_INDICATOR_LLM_OK_RATIO" in out
    assert "MIN_ONCHAIN_WALLET_LLM_OK_RATIO" in out
    assert "MIN_LARGE_LIQUIDATION_LLM_OK_RATIO" in out
    assert "MIN_SOCIAL_NEWS_LLM_OK_RATIO" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_HINT" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND" not in out
    assert "MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT" in out
    assert "MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT" in out
    assert "MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO" in out
    assert "WITH_AGENT_ACTION_HINT_CASES_REPORT" in out
    assert "AGENT_ACTION_HINT_CASES_REPORT_PATH" in out
    assert "AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" in out


def test_verify_nightly_help_contains_legacy_confidence_env() -> None:
    out = _run_help("tools/ci/verify_nightly.sh")
    assert "Usage:" in out
    assert "MAX_LEGACY_CONFIDENCE_RATIO" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out
    assert "MAX_PIPELINE_MODE_UNKNOWN_COUNT" in out
    assert "MAX_PIPELINE_MODE_MISSING_COUNT" in out
    assert "MAX_EVENT_TYPE_MATCH_MISSING_COUNT" in out
    assert "MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT" in out
    assert "MIN_EVENT_TYPE_MATCH_ALIAS_RATIO" in out
    assert "WITH_AGENT_DECISION_AGENT_KEY_REPORT" in out
    assert "AGENT_DECISION_AGENT_KEY_REPORT_PATH" in out
    assert "MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT" in out
    assert "MAX_DECISION_AGENT_KEY_GENERIC_RATIO" in out
    assert "WITH_AGENT_ROUTE_REPLAY_REPORT" in out
    assert "AGENT_ROUTE_REPLAY_REPORT_PATH" in out
    assert "MAX_ROUTE_REPLAY_MISMATCH_COUNT" in out
    assert "WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT" in out
    assert "MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO" in out
    assert "MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO" in out
    assert "MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO" in out
    assert "MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO" in out
    assert "MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT" in out
    assert "MIN_MARKET_INDICATOR_LLM_OK_RATIO" in out
    assert "MIN_ONCHAIN_WALLET_LLM_OK_RATIO" in out
    assert "MIN_LARGE_LIQUIDATION_LLM_OK_RATIO" in out
    assert "MIN_SOCIAL_NEWS_LLM_OK_RATIO" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH" in out
    assert "MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT" in out
    assert "MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT" in out
    assert "MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO" in out
    assert "MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT" in out
    assert "MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT" in out
    assert "MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT" in out
    assert "MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT" in out
    assert "WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT" in out
    assert "WITH_AGENT_ACTION_HINT_CASES_REPORT" in out
    assert "AGENT_ACTION_HINT_CASES_REPORT_PATH" in out
    assert "AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" in out


def test_verify_regression_and_nightly_call_event_type_summary_script() -> None:
    regression_text = (PROJECT_ROOT / "tools" / "ci" / "verify_regression.sh").read_text(encoding="utf-8")
    nightly_text = (PROJECT_ROOT / "tools" / "ci" / "verify_nightly.sh").read_text(encoding="utf-8")
    quick_text = (PROJECT_ROOT / "tools" / "ci" / "verify_quick.sh").read_text(encoding="utf-8")
    assert "tools/local/print_event_type_match_summary.sh" in regression_text
    assert "tools/local/print_event_type_match_summary.sh" in nightly_text
    assert "tools/local/print_decision_agent_key_summary.sh" in regression_text
    assert "tools/local/print_decision_agent_key_summary.sh" in nightly_text
    assert "tools/local/print_route_replay_summary.sh" in regression_text
    assert "tools/local/print_route_replay_summary.sh" in nightly_text
    assert "tools/local/print_action_hint_semantics_summary.sh" in regression_text
    assert "tools/local/print_action_hint_semantics_summary.sh" in nightly_text
    assert "tools/local/run_agent_decision_agent_key_report.sh" in regression_text
    assert "tools/local/run_agent_decision_agent_key_report.sh" in nightly_text
    assert "tools/local/run_agent_signal_decision_replay_report.sh" in regression_text
    assert "tools/local/run_agent_signal_decision_replay_report.sh" in nightly_text
    assert "tools/local/run_agent_signal_router_baseline_replay.sh" in regression_text
    assert "tools/local/print_signal_decision_quality_summary.sh" in regression_text
    assert "tools/local/print_signal_decision_quality_summary.sh" in nightly_text
    assert "tools/local/check_agent_signal_decision_replay_guard.sh" in regression_text
    assert "tools/local/check_agent_signal_decision_replay_guard.sh" in nightly_text
    assert "tools/local/check_agent_signal_decision_source_quality_guard.sh" in regression_text
    assert "tools/local/check_agent_signal_decision_source_quality_guard.sh" in nightly_text
    assert "tools/local/print_agent_signal_decision_replay_recommendation_hint.sh" in regression_text
    assert "tools/local/read_agent_signal_decision_recommendation_status.sh" in regression_text
    assert "tools/local/run_agent_signal_decision_llm_observe_report.sh" in regression_text
    assert "tools/local/print_signal_decision_llm_observe_summary.sh" in regression_text
    assert "tools/local/print_signal_decision_llm_observe_aggregate_summary.sh" in regression_text
    assert "--with-signal-decision-llm-observe-report" in regression_text
    assert "recommendation_artifact_status=" in regression_text
    assert "tools/local/print_agent_signal_decision_replay_trend.sh" in nightly_text
    assert "tools/local/check_agent_signal_decision_replay_trend_recommendation.sh" in nightly_text
    assert "tools/local/read_agent_signal_decision_recommendation_status.sh" in nightly_text
    assert "tools/local/run_agent_signal_decision_llm_observe_report.sh" in nightly_text
    assert "tools/local/print_signal_decision_llm_observe_summary.sh" in nightly_text
    assert "tools/local/print_signal_decision_llm_observe_agent_key_coverage.sh" in nightly_text
    assert "tools/local/print_signal_decision_llm_observe_agent_key_trend.sh" in nightly_text
    assert "tools/local/print_signal_decision_llm_observe_trend_recommendation_hint.sh" in nightly_text
    assert "tools/local/print_signal_decision_llm_observe_aggregate_summary.sh" in nightly_text
    assert "tools/local/run_agent_signal_router_baseline_replay.sh" in nightly_text
    assert "llm_observe_trend_recommendation_status=" in nightly_text
    assert "--with-signal-decision-llm-observe-report" in nightly_text
    assert "recommendation_artifact_status=" in nightly_text
    assert "tools/local/check_agent_decision_agent_key_report_guard.sh" in regression_text
    assert "tools/local/check_agent_decision_agent_key_report_guard.sh" in nightly_text
    assert "tools/local/inspect_agent_action_hint_cases.sh" in quick_text
    assert "tools/local/print_route_replay_summary.sh" in quick_text
    assert "tools/local/run_agent_signal_router_baseline_replay.sh" in quick_text
    assert "tools/local/run_agent_signal_decision_replay_report.sh" in quick_text
    assert "tools/local/print_signal_decision_quality_summary.sh" in quick_text
    assert "tools/local/print_signal_decision_replay_summary.sh" in quick_text
    assert "tools/local/check_agent_signal_decision_replay_guard.sh" in quick_text
    assert "tools/local/check_agent_signal_decision_source_quality_guard.sh" in quick_text
    assert "tools/local/inspect_agent_action_hint_cases.sh" in regression_text
    assert "tools/local/inspect_agent_action_hint_cases.sh" in nightly_text
    assert "--status missing" in regression_text
    assert "--status missing" in nightly_text


def test_verify_quick_help_contains_optional_agent_readyz_env() -> None:
    out = _run_help("tools/ci/verify_quick.sh")
    assert "Usage:" in out
    assert "WITH_AGENT_READYZ=1" in out
    assert "WITH_AGENT_ROUTING_GUARDS=1" in out
    assert "WITH_PIPELINE_MODE_REPORT=1" in out
    assert "WITH_AGENT_CLOSED_LOOP_SMOKE=1" in out
    assert "WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1" in out
    assert "WITH_AGENT_ACTION_HINT_CASES_REPORT=1" in out
    assert "WITH_AGENT_DECISION_AGENT_KEY_REPORT=1" in out
    assert "WITH_AGENT_ROUTE_REPLAY_REPORT=1" in out
    assert "WITH_AGENT_SIGNAL_ROUTER_BASELINE_REPLAY=1" in out
    assert "WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT=1" in out
    assert "AGENT_ACTION_HINT_CASES_REPORT_PATH" in out
    assert "AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH" in out
    assert "AGENT_DECISION_AGENT_KEY_REPORT_PATH" in out
    assert "AGENT_ROUTE_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_SAMPLES_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_ROUTER_BASELINE_REPLAY_STRICT" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH" in out
    assert "AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT" in out
    assert "MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO" in out
    assert "MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO" in out
    assert "MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO" in out
    assert "MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO" in out
    assert "MIN_SIGNAL_DECISION_SOURCE_QUALITY_MIN_SOURCE_COUNT" in out
    assert "MIN_MARKET_INDICATOR_LLM_OK_RATIO" in out
    assert "MIN_ONCHAIN_WALLET_LLM_OK_RATIO" in out
    assert "MIN_LARGE_LIQUIDATION_LLM_OK_RATIO" in out
    assert "MIN_SOCIAL_NEWS_LLM_OK_RATIO" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out
    assert "MAX_PIPELINE_MODE_UNKNOWN_COUNT" in out
    assert "MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT" in out
    assert "MAX_DECISION_AGENT_KEY_GENERIC_RATIO" in out
    assert "MAX_ROUTE_REPLAY_MISMATCH_COUNT" in out


def test_verify_local_quick_help_contains_agent_readyz_options() -> None:
    out = _run_help("tools/local/verify_quick.sh")
    assert "Usage:" in out
    assert "--with-agent-readyz" in out
    assert "--with-agent-closed-loop-smoke" in out
    assert "--with-agent-action-hint-semantics-report" in out
    assert "--with-agent-action-hint-cases-report" in out
    assert "--with-agent-decision-agent-key-report" in out
    assert "--with-agent-route-replay-report" in out
    assert "--with-agent-signal-decision-replay-report" in out
    assert "--agent-action-hint-cases-report-path <path>" in out
    assert "--agent-action-hint-missing-cases-report-path <path>" in out
    assert "--agent-decision-agent-key-report-path <path>" in out
    assert "--agent-route-replay-report-path <path>" in out
    assert "--agent-signal-decision-replay-report-path <path>" in out
    assert "--agent-signal-decision-replay-min-source-count <int>" in out
    assert "--max-market-indicator-rule-fallback-ratio <float>" in out
    assert "--max-onchain-wallet-rule-fallback-ratio <float>" in out
    assert "--max-large-liquidation-rule-fallback-ratio <float>" in out
    assert "--max-social-news-rule-fallback-ratio <float>" in out
    assert "--max-decision-agent-key-unknown-count <int>" in out
    assert "--max-route-replay-mismatch-count <int>" in out
