from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import asyncio
from dataclasses import asdict

from services.agent_server_new.adapters.market_state_http import _build_msl_from_dict
from services.agent_server_new.app.context_builder import ContextBuilder
from services.agent_server_new.domain.contracts import Confidence, ExecutionPlan, RiskAllowance
from services.agent_server_new.observability.decision_trace import map_alert_codes_from_contract_warnings
from services.agent_server_new.ports.market_state import MarketStateSnapshot
from services.execution_service.adapters.agent_execution_plan_adapter import (
    adapt_agent_execution_plan_to_decision_intent,
)
from services.market_state_engine.src.service import MarketStateService
from verification.fixtures.execution_service.stub_risk_policy_provider import StubRiskPolicyProvider
from verification.fixtures.execution_service.stub_state_providers import (
    StubAccountStateProvider,
    StubPositionStateProvider,
)
from services.execution_service.app.service import ExecutionService


class _SemanticRawProvider:
    async def get_raw_structure(self, exchange: str, symbol: str):  # noqa: ARG002
        return {
            "symbol": symbol,
            "horizons": {
                "fused": {
                    "horizons": {
                        "short_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "medium"}}},
                        "mid_term": {
                            "market_background": {"trend_memory": {"price_direction": "up", "price_strength": "strong"}},
                            "participant_background": {"crowding": "normal", "stability": "stable"},
                        },
                        "long_term": {"market_background": {"trend_memory": {"price_direction": "up", "price_strength": "medium"}}},
                    }
                }
            },
            "pre_decision_structure": {
                "short_term": {
                    "micro_liquidity": {
                        "meta": {"stability": "fragile"},
                        "risk_flags": {"liquidity_vacuum_event": True, "depth_imbalance": 1},
                    },
                    "structural_risks": {"liquidity_vacuum": True},
                },
                "mid_term": {
                    "participant_positioning": {
                        "oi_delta": {"delta_oi_pct": 0.05},
                        "oi_dynamics": {"oi_trend": "up", "oi_velocity": "high", "oi_acceleration": "up"},
                        "risk_flags": {"fragile_leverage_build": True, "possible_liquidation_or_unwind": 1},
                    }
                },
                "long_term": {"structural_context": {"trend_maturity": "mid"}},
            },
            "alternative_sources": {
                "news": {"source_type": "news", "available": True, "provider_state": "primary", "features": {"headline_score": 0.7}},
                "onchain": {"source_type": "onchain", "available": True, "provider_state": "noop", "features": {}},
            },
        }


class _SemanticSelectedEventProvider:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20):  # noqa: ARG002
        return [
            {
                "asset": f"{exchange}:{symbol}",
                "ts_ms": 1710000000000,
                "selected_type": "onchain.alert",
                "direction_hint": "mixed",
                "priority": "medium",
                "context_snapshot": {
                    "alternative_sources_summary": {
                        "available_sources": ["onchain"],
                        "unavailable_sources": ["news", "social"],
                        "provider_states": {"news": "empty", "social": "empty", "onchain": "event_evidence_present"},
                        "data_sources": {
                            "news": "event_center_new.news",
                            "social": "event_center_new.social",
                            "onchain": "event_center_new.onchain",
                        },
                        "inference_sources": {
                            "news": "event_center_new.selector",
                            "social": "event_center_new.selector",
                            "onchain": "event_center_new.selector",
                        },
                        "feature_keys": {"news": [], "social": [], "onchain": ["inflow_usd"]},
                        "evidence_counts": {"news": 0, "social": 0, "onchain": 2},
                    }
                },
                "trace": {"schema_version": "selected-v2"},
                "route": {"to": "market_state_engine"},
            }
        ]


class _SemanticRawProviderInvalidProviderState:
    async def get_raw_structure(self, exchange: str, symbol: str):  # noqa: ARG002
        return {
            "symbol": symbol,
            "horizons": {"fused": {"horizons": {}}},
            "pre_decision_structure": {},
            "alternative_sources": {
                "onchain": {
                    "source_type": "onchain",
                    "available": True,
                    "provider_state": "BAD_STATE",
                    "features": {"inflow_usd": 123456.0},
                }
            },
        }


class _MarketStateFromService:
    def __init__(self, payload: dict) -> None:
        self._payload = dict(payload)

    async def get_market_state(self, exchange: str, symbol: str):  # noqa: ARG002
        p = dict(self._payload)
        return MarketStateSnapshot(
            exchange=str(p.get("exchange") or exchange),
            symbol=str(p.get("symbol") or symbol),
            msl=_build_msl_from_dict(dict(p.get("msl") or {})),
            msl_meta=dict(p.get("msl_meta") or {}),
            msl_bundle=dict(p.get("msl_bundle") or {}),
            msl_bundle_meta=dict(p.get("msl_bundle_meta") or {}),
            cross_horizon=dict(p.get("cross_horizon") or {}),
            state_features=dict(p.get("state_features") or {}),
            anomaly_flags=[str(x) for x in list(p.get("anomaly_flags") or []) if x],
            raw_market_structure=dict(p.get("raw_market_structure") or {}),
        )


class _PositionContext:
    async def get_position_context(self, exchange: str, symbol: str):  # noqa: ARG002
        return {"has_position": False}


class _ActiveEvents:
    async def get_active_events(self, exchange: str, symbol: str):  # noqa: ARG002
        return []


def test_agent_plan_to_execution_service_smoke() -> None:
    plan = ExecutionPlan(
        action="add",
        direction="long",
        allowance=RiskAllowance(
            allow_open=True,
            allow_add=True,
            allow_reduce=True,
            allow_exit=True,
            reasons=[],
        ),
        confidence=Confidence(level="medium", score=0.65),
        notes="agent建议顺势尝试开仓",
    )
    decision_payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-001",
        exchange="binance",
        symbol="ETHUSDT",
        plan=asdict(plan),
        cross_horizon_policy={"suggested_policy": "follow_long_term"},
    )
    service = ExecutionService(
        position_provider=StubPositionStateProvider(),
        account_provider=StubAccountStateProvider(),
        risk_policy_provider=StubRiskPolicyProvider(),
    )
    result = asyncio.run(service.decide(decision_payload))
    assert result.decision_id == "dec-agent-001"
    assert result.execution_action in {"add", "reduce", "hold", "exit", "skip"}


def test_agent_execution_adapter_prefers_decision_confidence_and_keeps_risk_hints() -> None:
    payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-002",
        exchange="binance",
        symbol="ETHUSDT",
        plan={
            "action": "add",
            "direction": "long",
            "confidence": {"level": "low", "score": 0.2},
            "decision_confidence": {"level": "high", "score": 0.91},
            "notes": "prefer trend continuation",
        },
        cross_horizon_policy={"suggested_policy": "follow_long_term"},
    )
    assert payload["decision_confidence"] == {"level": "high", "score": 0.91}
    assert "confidence" not in payload
    assert payload["risk_hints"]["decision_confidence"] == {"level": "high", "score": 0.91}
    assert payload["risk_hints"]["decision_confidence_source"] == "decision_confidence"
    assert payload["risk_hints"]["agent_action_hint"] == "add"
    assert payload["risk_hints"]["agent_notes"] == "prefer trend continuation"


def test_agent_execution_adapter_marks_legacy_confidence_source() -> None:
    payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-003",
        exchange="binance",
        symbol="ETHUSDT",
        plan={
            "action": "hold",
            "direction": "none",
            "confidence": {"level": "medium", "score": 0.5},
        },
        cross_horizon_policy={},
    )
    assert payload["decision_confidence"] == {"level": "medium", "score": 0.5}
    assert "confidence" not in payload
    assert payload["risk_hints"]["decision_confidence_source"] == "confidence_legacy"


def test_agent_execution_adapter_normalizes_none_direction_to_neutral() -> None:
    payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-003b",
        exchange="binance",
        symbol="ETHUSDT",
        plan={
            "action": "hold",
            "direction": "none",
            "confidence": {"level": "medium", "score": 0.5},
        },
        cross_horizon_policy={},
    )
    assert payload["direction_intent"] == "neutral"


def test_agent_execution_adapter_normalizes_alternative_source_summary_in_risk_hints() -> None:
    payload = adapt_agent_execution_plan_to_decision_intent(
        decision_id="dec-agent-004",
        exchange="binance",
        symbol="ETHUSDT",
        plan={
            "action": "add",
            "direction": "long",
            "decision_confidence": {"level": "medium", "score": 0.6},
            "alternative_source_summary": {
                "available_sources": ["onchain", "noise", "news"],
                "provider_states": {"onchain": "event_evidence_present", "news": "primary", "x": "bad"},
                "data_sources": {"onchain": "event_center_new.onchain", "news": "feature_service.news"},
                "inference_sources": {"onchain": "event_center_new.selector", "news": "feature_service.normalizer"},
                "feature_keys": {"onchain": ["inflow_usd", "inflow_usd"], "news": ["headline_score"]},
                "evidence_counts": {"onchain": 2, "news": "1", "social": -2},
                "debug_only": {"x": 1},
            },
        },
        cross_horizon_policy={},
    )
    hints = dict(payload.get("risk_hints") or {})
    alt = dict(hints.get("alternative_source_summary") or {})
    assert set(alt.keys()) >= {
        "available_sources",
        "unavailable_sources",
        "provider_states",
        "data_sources",
        "inference_sources",
        "feature_keys",
        "evidence_counts",
    }
    assert alt.get("available_sources") == ["news", "onchain"]
    assert dict(alt.get("provider_states") or {}).get("onchain") == "event_evidence_present"
    assert dict(alt.get("provider_states") or {}).get("social") == ""
    assert dict(alt.get("evidence_counts") or {}).get("social") == 0
    assert "debug_only" not in alt


def test_semantic_chain_smoke_provider_state_risk_flags_and_decision_confidence() -> None:
    async def _run() -> None:
        state_service = MarketStateService(
            raw_structure_provider=_SemanticRawProvider(),
            selected_event_provider=_SemanticSelectedEventProvider(),
        )
        state_payload = await state_service.get_market_state("binance", "ETHUSDT")

        # state 层：risk_flags 已归一化为 list；alternative_sources 融合结果语义稳定。
        open_interest = dict((state_payload.get("state_features") or {}).get("open_interest") or {})
        assert isinstance(open_interest.get("risk_flags"), list)
        assert "fragile_leverage_build" in list(open_interest.get("risk_flags") or [])
        fusion = dict(((state_payload.get("state_features") or {}).get("evidence") or {}).get("alternative_sources_fusion") or {})
        by_source = dict(dict(fusion.get("merged") or {}).get("by_source") or {})
        news = dict(by_source.get("news") or {})
        onchain = dict(by_source.get("onchain") or {})
        assert news.get("provider_state") == "primary"
        assert news.get("data_source") == "feature_service.news"
        assert news.get("inference_source") == "feature_service.normalizer"
        assert onchain.get("provider_state") == "event_evidence_present"
        assert onchain.get("data_source") == "event_center_new.onchain"
        assert onchain.get("inference_source") == "event_center_new.selector"

        # agent 上下文：应输出语义稳定的 alternative_source_summary 和 oi_risk_flags。
        context_builder = ContextBuilder(
            market_state=_MarketStateFromService(state_payload),
            position_context=_PositionContext(),
            active_events=_ActiveEvents(),
            max_key_features=20,
        )
        built = await context_builder.build(
            event_id="sem-chain-001",
            exchange="binance",
            symbol="ETHUSDT",
            signal_payload={"event_type": "indicator_signal"},
        )
        features = list((built.ctx.key_market_features or {}).get("features") or [])
        by_name = {str(item.get("name")): item.get("value") for item in features}
        alt_summary = dict(by_name.get("alternative_source_summary") or {})
        assert "news" in list(alt_summary.get("available_sources") or [])
        assert "onchain" in list(alt_summary.get("available_sources") or [])
        assert dict(alt_summary.get("provider_states") or {}).get("news") == "primary"
        assert dict(alt_summary.get("provider_states") or {}).get("onchain") == "event_evidence_present"
        assert dict(alt_summary.get("data_sources") or {}).get("news") == "feature_service.news"
        assert dict(alt_summary.get("inference_sources") or {}).get("news") == "feature_service.normalizer"
        assert dict(alt_summary.get("data_sources") or {}).get("onchain") == "event_center_new.onchain"
        assert dict(alt_summary.get("inference_sources") or {}).get("onchain") == "event_center_new.selector"
        assert "fragile_leverage_build" in list(by_name.get("oi_risk_flags") or [])

        # execution 输入：只使用 canonical decision_confidence。
        plan = ExecutionPlan(
            action="add",
            direction="long",
            allowance=RiskAllowance(
                allow_open=True,
                allow_add=True,
                allow_reduce=True,
                allow_exit=True,
                reasons=[],
            ),
            confidence=Confidence(level="medium", score=0.66),
            notes="semantic_chain_smoke",
        )
        decision_payload = adapt_agent_execution_plan_to_decision_intent(
            decision_id="sem-chain-dec-001",
            exchange="binance",
            symbol="ETHUSDT",
            plan=asdict(plan),
            cross_horizon_policy=dict(state_payload.get("cross_horizon") or {}),
        )
        assert "confidence" not in decision_payload
        assert decision_payload.get("decision_confidence") == {"level": "medium", "score": 0.66}

        execution_service = ExecutionService(
            position_provider=StubPositionStateProvider(),
            account_provider=StubAccountStateProvider(),
            risk_policy_provider=StubRiskPolicyProvider(),
        )
        result = await execution_service.decide(decision_payload)
        assert result.decision_id == "sem-chain-dec-001"
        assert result.execution_action in {"add", "reduce", "hold", "exit", "skip"}
        assert decision_payload.get("risk_hints", {}).get("decision_confidence_source") == "confidence_legacy"

    asyncio.run(_run())


def test_semantic_chain_smoke_invalid_provider_state_warning_and_alert_code() -> None:
    async def _run() -> None:
        state_service = MarketStateService(
            raw_structure_provider=_SemanticRawProviderInvalidProviderState(),
            selected_event_provider=_SemanticSelectedEventProvider(),
        )
        state_payload = await state_service.get_market_state("binance", "ETHUSDT")

        anomaly_flags = list(state_payload.get("anomaly_flags") or [])
        assert "state_features_alternative_source_provider_state_invalid" in anomaly_flags

        context_builder = ContextBuilder(
            market_state=_MarketStateFromService(state_payload),
            position_context=_PositionContext(),
            active_events=_ActiveEvents(),
            max_key_features=20,
        )
        built = await context_builder.build(
            event_id="sem-chain-invalid-001",
            exchange="binance",
            symbol="ETHUSDT",
            signal_payload={"event_type": "indicator_signal"},
        )
        contract_warnings = list((built.ctx.key_market_features or {}).get("contract_warnings") or [])
        assert "state_features_alternative_source_provider_state_invalid" in contract_warnings
        assert "alternative_sources_provider_state_invalid" in contract_warnings

        alert_codes = map_alert_codes_from_contract_warnings(contract_warnings)
        assert "AGENT_ALTERNATIVE_SOURCES_PROVIDER_STATE_INVALID" in alert_codes

    asyncio.run(_run())
