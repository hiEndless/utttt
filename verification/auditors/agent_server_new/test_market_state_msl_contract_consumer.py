import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.workflows.trade_event_workflow import _msl_from_dict


MSL_ALLOWED_KEYS = {
    "version",
    "timestamp",
    "symbol",
    "market_regime",
    "liquidity_state",
    "positioning_state",
    "volatility_state",
    "risk_state",
    "market_structure_state",
    "key_levels",
    "anomalies",
    "summary",
}


def _sample_msl_payload() -> dict:
    return {
        "version": 2,
        "timestamp": "2026-03-09T12:00:00Z",
        "symbol": "ETHUSDT",
        "market_regime": {
            "trend": "bullish",
            "phase": "continuation",
            "timeframe_alignment": "aligned",
            "strength": 0.75,
        },
        "liquidity_state": {
            "dominant_pressure": "buyers",
            "liquidity_risk": "neutral",
            "orderbook_bias": "neutral",
            "liquidation_proximity": "none",
        },
        "positioning_state": {
            "crowding": "balanced",
            "whale_bias": "unknown",
            "retail_bias": "unknown",
            "oi_trend": "expanding",
        },
        "volatility_state": {
            "volatility_regime": "normal",
            "expansion_risk": "unknown",
            "volatility_direction": "upside",
        },
        "risk_state": {
            "cascade_risk": "low",
            "squeeze_probability": "low",
            "reversal_risk": "low",
        },
        "market_structure_state": {
            "support_strength": "unknown",
            "resistance_strength": "unknown",
            "range_state": "breakout",
            "trend_structure": "hh_hl",
        },
        "key_levels": {"major_support": [], "major_resistance": [], "liquidation_clusters": []},
        "anomalies": [],
        "summary": "bullish continuation.",
    }


def test_http_adapter_msl_parser_keeps_structural_whitelist_only():
    payload = _sample_msl_payload()
    # 即使上游误带旧字段，解析后也应被忽略，不进入 to_llm_dict 输出。
    payload["sentiment_state"] = {
        "funding_sentiment": "unknown",
        "social_sentiment": "unknown",
        "news_bias": "unknown",
        "overall_sentiment": "unknown",
    }
    msl = _build_msl_from_dict(payload)
    out = msl.to_llm_dict()
    assert set(out.keys()) == MSL_ALLOWED_KEYS
    assert "sentiment_state" not in out


def test_workflow_msl_parser_keeps_structural_whitelist_only():
    payload = _sample_msl_payload()
    payload["sentiment_state"] = {"news_bias": "unknown"}
    msl = _msl_from_dict(payload)
    out = msl.to_llm_dict()
    assert set(out.keys()) == MSL_ALLOWED_KEYS
    assert "sentiment_state" not in out
