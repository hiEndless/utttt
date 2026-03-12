import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.market_state_engine.src.engine import MarketStateEngine
from services.market_state_engine.src.state_inference.engine import infer_msl_from_features, infer_msl_with_meta


def _sample_market_structure() -> dict:
    return {
        "horizons": {
            "fused": {
                "horizons": {
                    "short_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "medium"}}},
                    "mid_term": {
                        "market_background": {
                            "trend_memory": {"price_direction": "up", "price_strength": "strong"},
                            "trend_context": {"label": "trend_continuation"},
                            "volatility_state": "normal",
                        },
                        "participant_background": {"crowding": "normal", "stability": "stable"},
                    },
                    "long_term": {"market_background": {}},
                }
            }
        },
        "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
    }


def _sample_market_structure_with_horizon_conflict() -> dict:
    return {
        "horizons": {
            "fused": {
                "horizons": {
                    "short_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "strong"}}},
                    "mid_term": {"market_background": {"trend_memory": {"price_direction": "flat", "price_strength": "weak"}}},
                    "long_term": {"market_background": {"trend_memory": {"price_direction": "down", "price_strength": "strong"}}},
                }
            }
        },
        "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
    }


def test_state_inference_default_pipeline_generates_contract_fields():
    engine = MarketStateEngine()
    msl, _features = engine.build(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    payload = msl.to_llm_dict()
    assert payload["market_regime"]["trend"] in {"bullish", "bearish", "sideways", "unknown"}
    assert payload["liquidity_state"]["dominant_pressure"] in {"buyers", "sellers", "balanced", "unknown"}
    assert "plugin_warnings" in dict(msl.evidence or {})


def test_aggregate_features_keeps_legacy_and_explicit_horizon_confidence() -> None:
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure={
            "horizons": {
                "fused": {
                    "horizons": {
                        "short_term": {"confidence": 0.7},
                        "mid_term": {"confidence": 0.5},
                        "long_term": {"confidence": 0.3},
                    }
                }
            },
            "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
        },
    )
    for hz in ("short_term", "mid_term", "long_term"):
        node = dict(features.horizons.get(hz) or {})
        assert "confidence" in node
        assert "horizon_confidence" in node
        assert node["horizon_confidence"] == node["confidence"]


def test_aggregate_features_normalizes_risk_flags_and_keeps_risk_metrics() -> None:
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure={
            "horizons": {"fused": {"horizons": {"short_term": {}, "mid_term": {}, "long_term": {}}}},
            "pre_decision_structure": {
                "short_term": {
                    "micro_liquidity": {
                        "meta": {"stability": "stable"},
                        "risk_flags": {
                            "liquidity_vacuum_event": True,
                            "depth_thin": "true",
                            "noise": "false",
                        },
                    },
                    "structural_risks": {},
                },
                "mid_term": {
                    "participant_positioning": {
                        "risk_flags": ["possible_liquidation_or_unwind", "possible_liquidation_or_unwind", "fragile_leverage_build"],
                    }
                },
                "long_term": {},
            },
        },
    )
    orderbook = dict(features.orderbook or {})
    open_interest = dict(features.open_interest or {})
    assert orderbook["risk_flags"] == ["depth_thin", "liquidity_vacuum_event"]
    assert isinstance(orderbook["risk_metrics"], dict)
    assert orderbook["risk_metrics"]["liquidity_vacuum_event"] is True
    assert "noise" not in set(orderbook["risk_flags"])
    assert open_interest["risk_flags"] == ["fragile_leverage_build", "possible_liquidation_or_unwind"]


def test_state_inference_plugin_exception_degrades_to_warning():
    class _BoomPlugin:
        name = "boom_plugin"
        order = 5

        def infer(self, *, features, context):  # noqa: ANN001
            raise RuntimeError("boom")

    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(features=features, plugins=[_BoomPlugin()])
    warnings = [str(x) for x in list(dict(msl.evidence or {}).get("plugin_warnings") or []) if x]
    assert any("boom_plugin" in x and "boom" in x for x in warnings)


def test_state_inference_disabled_plugins_take_effect():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(
        features=features,
        plugin_config={"disabled_plugins": ["structure_inference"]},
    )
    payload = msl.to_llm_dict()
    assert payload["market_structure_state"]["range_state"] == "unknown"
    assert payload["market_structure_state"]["trend_structure"] == "unknown"


def test_state_inference_enabled_plugins_whitelist_mode():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(
        features=features,
        plugin_config={"enabled_plugins": ["regime_inference"]},
    )
    payload = msl.to_llm_dict()
    assert payload["market_regime"]["trend"] in {"bullish", "bearish", "sideways", "unknown"}
    assert payload["liquidity_state"]["dominant_pressure"] == "unknown"


def test_state_inference_fast_mode_profile_disables_structure_plugin():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(
        features=features,
        plugin_config={"plugin_profile": "fast_mode"},
    )
    payload = msl.to_llm_dict()
    assert payload["market_structure_state"]["range_state"] == "unknown"
    assert payload["market_structure_state"]["trend_structure"] == "unknown"


def test_state_inference_enabled_plugins_override_profile():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(
        features=features,
        plugin_config={
            "plugin_profile": "risk_only",
            "enabled_plugins": ["regime_inference", "structure_inference"],
        },
    )
    payload = msl.to_llm_dict()
    assert payload["market_structure_state"]["range_state"] in {"breakout", "range", "breakdown", "unknown"}


def test_state_inference_custom_profiles_file_takes_effect():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "profiles.json"
        p.write_text('{"custom_min":["regime_inference"]}', encoding="utf-8")
        msl = infer_msl_from_features(
            features=features,
            plugin_config={
                "plugin_profile": "custom_min",
                "profiles_file": str(p),
            },
        )
    payload = msl.to_llm_dict()
    assert payload["market_regime"]["trend"] in {"bullish", "bearish", "sideways", "unknown"}
    assert payload["liquidity_state"]["dominant_pressure"] == "unknown"


def test_state_inference_risk_only_profile_is_minimal_chain():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl = infer_msl_from_features(
        features=features,
        plugin_config={"plugin_profile": "risk_only"},
    )
    payload = msl.to_llm_dict()
    # risk_only 仅保留 regime+risk 主链路，流动性/结构推断应回退 unknown。
    assert payload["liquidity_state"]["dominant_pressure"] == "unknown"
    assert payload["market_structure_state"]["range_state"] == "unknown"
    # 风险字段仍应由 risk 插件给出有效等级（至少不是缺失）。
    assert payload["risk_state"]["cascade_risk"] in {"high", "medium", "low", "unknown"}


def test_state_inference_multi_generator_same_schema():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    msl_v1, meta_v1 = infer_msl_with_meta(
        features=features,
        plugin_config={"inference_version": "msl_generator_v1"},
    )
    msl_v2, meta_v2 = infer_msl_with_meta(
        features=features,
        plugin_config={"inference_version": "msl_generator_v2"},
    )
    assert set(msl_v1.to_llm_dict().keys()) == set(msl_v2.to_llm_dict().keys())
    assert int(msl_v1.version) == 2 and int(msl_v2.version) == 2
    assert meta_v1["schema_version"] == 2 and meta_v2["schema_version"] == 2
    assert meta_v1["inference_version"] == "msl_generator_v1"
    assert meta_v2["inference_version"] == "msl_generator_v2"


def test_state_inference_unknown_generator_fallback_to_v1():
    engine = MarketStateEngine()
    features = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure(),
    )
    _msl, meta = infer_msl_with_meta(
        features=features,
        plugin_config={"inference_version": "msl_generator_v999"},
    )
    assert meta["inference_version_requested"] == "msl_generator_v999"
    assert meta["inference_version"] == "msl_generator_v1"


def test_multi_horizon_bundle_detects_trend_conflict():
    engine = MarketStateEngine()
    feats0 = engine.aggregate_features(
        exchange="binance",
        symbol="ETHUSDT",
        market_structure=_sample_market_structure_with_horizon_conflict(),
    )
    anomalies = engine.detect_anomalies(features=feats0)
    evidence = engine.extract_evidence(features=feats0, anomalies=anomalies)
    features = type(feats0)(
        exchange=feats0.exchange,
        symbol=feats0.symbol,
        ts=feats0.ts,
        horizons=feats0.horizons,
        orderbook=feats0.orderbook,
        open_interest=feats0.open_interest,
        anomalies=anomalies,
        evidence=evidence,
        derived=feats0.derived,
    )
    bundle, _bundle_meta, cross = engine.infer_multi_horizon_msl(features=features)
    assert set(bundle.keys()) == {"short_term", "mid_term", "long_term"}
    assert cross["alignment"] in {"conflicting", "mixed", "aligned", "unknown"}
    assert any(c.get("field") == "trend" for c in list(cross.get("conflicts") or []))
    assert cross.get("suggested_policy") in {"wait_confirmation", "reduce_risk", "follow_long_term", "no_action"}


def test_cross_horizon_conflict_priority_for_multiple_fields():
    engine = MarketStateEngine()
    bundle = {
        "short_term": {
            "market_regime": {"trend": "bullish", "phase": "impulse"},
            "volatility_state": {"volatility_regime": "high"},
            "liquidity_state": {"liquidity_risk": "short_squeeze"},
        },
        "mid_term": {
            "market_regime": {"trend": "sideways", "phase": "continuation"},
            "volatility_state": {"volatility_regime": "normal"},
            "liquidity_state": {"liquidity_risk": "neutral"},
        },
        "long_term": {
            "market_regime": {"trend": "bearish", "phase": "distribution"},
            "volatility_state": {"volatility_regime": "low"},
            "liquidity_state": {"liquidity_risk": "long_squeeze"},
        },
    }
    cross = engine._build_cross_horizon(bundle)  # noqa: SLF001
    assert cross["alignment"] == "conflicting"
    assert cross["suggested_policy"] == "wait_confirmation"
    assert cross["policy_reason"] == "short_long_trend_conflict"
    fields = [str(x.get("field")) for x in list(cross.get("conflicts") or [])]
    assert fields[:4] == ["trend", "phase", "volatility_regime", "liquidity_risk"]


def test_cross_horizon_policy_when_aligned():
    engine = MarketStateEngine()
    bundle = {
        "short_term": {"market_regime": {"trend": "bullish", "phase": "continuation"}},
        "mid_term": {"market_regime": {"trend": "bullish", "phase": "continuation"}},
        "long_term": {"market_regime": {"trend": "bullish", "phase": "continuation"}},
    }
    cross = engine._build_cross_horizon(bundle)  # noqa: SLF001
    assert cross["alignment"] == "aligned"
    assert cross["suggested_policy"] == "follow_long_term"
    assert cross["policy_reason"] == "timeframe_aligned"
