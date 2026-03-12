from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.adapters.active_events_redis import RedisActiveEventsProvider
from agent_server_new.adapters.market_state_http import _build_msl_from_dict
from agent_server_new.app.workflows.trade_event_workflow import TradeEventInput, TradeEventWorkflow
from agent_server_new.domain.contracts import ActionIntent, Confidence, ExecutionPlan, RiskAllowance, RulePlan, SignalVerdict
from agent_server_new.domain.strategy_gate import StrategyGateResult
from agent_server_new.ports.market_state import MarketStateSnapshot
from services.market_state_engine.src.service import MarketStateService


def _sample_raw_market_structure() -> Dict[str, Any]:
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
                    "long_term": {"market_background": {"trend_memory": {"price_direction": "down", "price_strength": "medium"}}},
                }
            }
        },
        "pre_decision_structure": {"short_term": {}, "mid_term": {}, "long_term": {}},
    }


def _sample_selected_events() -> List[Dict[str, Any]]:
    return [
        {
            "event_id": "sel-001",
            "asset": "binance:ETHUSDT",
            "selected_type": "onchain_alert",
            "direction_hint": "bullish",
            "priority": "high",
            "context_snapshot": {"source_reason": "whale_inflow"},
            "route": {"horizon": "5m"},
        }
    ]


class _RawStructureProvider:
    async def get_raw_structure(self, exchange: str, symbol: str) -> Dict[str, Any]:
        _ = (exchange, symbol)
        return _sample_raw_market_structure()


class _SelectedEventProvider:
    async def get_selected_events(self, exchange: str, symbol: str, *, limit: int = 20) -> List[Dict[str, Any]]:
        _ = (exchange, symbol)
        return _sample_selected_events()[: max(1, int(limit))]


class _InProcessMarketStateProvider:
    def __init__(self) -> None:
        self._service = MarketStateService(
            raw_structure_provider=_RawStructureProvider(),
            selected_event_provider=_SelectedEventProvider(),
        )

    async def get_market_state(self, exchange: str, symbol: str) -> MarketStateSnapshot:
        payload = await self._service.get_market_state(exchange, symbol)
        return MarketStateSnapshot(
            exchange=str(payload.get("exchange") or exchange),
            symbol=str(payload.get("symbol") or symbol),
            msl=_build_msl_from_dict(dict(payload.get("msl") or {})),
            msl_meta=dict(payload.get("msl_meta") or {}),
            msl_bundle=dict(payload.get("msl_bundle") or {}),
            msl_bundle_meta=dict(payload.get("msl_bundle_meta") or {}),
            cross_horizon=dict(payload.get("cross_horizon") or {}),
            state_features=dict(payload.get("state_features") or {}),
            anomaly_flags=[str(x) for x in list(payload.get("anomaly_flags") or []) if x],
            raw_market_structure=dict(payload.get("raw_market_structure") or {}),
        )


class _ActiveEventsFromSelectedProvider:
    async def get_active_events(self, exchange: str, symbol: str) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for item in _sample_selected_events():
            normalized = RedisActiveEventsProvider._normalize_active_event(  # noqa: SLF001
                item,
                stream_id=str(item.get("event_id") or "selected-stream-id"),
                exchange=exchange,
                symbol=symbol,
            )
            if normalized:
                out.append(normalized)
        return out


class _PositionProvider:
    async def get_position_context(self, exchange: str, symbol: str) -> Dict[str, Any]:
        _ = (exchange, symbol)
        return {"has_position": False}


class _Recorder:
    def __init__(self) -> None:
        self.market_context: Dict[str, Dict[str, Any]] = {}
        self.agent_outputs: List[Dict[str, Any]] = []

    async def record_market_context(self, event_id: str, payload: Dict[str, Any]) -> None:
        self.market_context[event_id] = dict(payload or {})

    async def record_agent_output(self, event_id: str, agent_name: str, payload: Dict[str, Any]) -> None:
        self.agent_outputs.append({"event_id": event_id, "agent_name": agent_name, "payload": dict(payload or {})})

    def get_agent_payload(self, event_id: str, agent_name: str) -> Dict[str, Any]:
        for item in reversed(self.agent_outputs):
            if item.get("event_id") == event_id and item.get("agent_name") == agent_name:
                return dict(item.get("payload") or {})
        return {}


def test_pipeline_traceability_selected_event_to_decision_trace():
    async def _run(monkeypatch):  # noqa: ANN001
        import agent_server_new.app.workflows.trade_event_workflow as mod

        # 中文注释：固定领域输出，避免测试受策略逻辑波动影响。
        monkeypatch.setattr(
            mod,
            "evaluate_signal",
            lambda **kwargs: SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="high", score=0.9)),
        )
        monkeypatch.setattr(
            mod,
            "resolve_intent",
            lambda **kwargs: ActionIntent(intent="increase", direction="long", confidence=Confidence(level="high", score=0.9)),
        )
        monkeypatch.setattr(
            mod,
            "build_rule_plan",
            lambda **kwargs: RulePlan(intent=kwargs["intent"], sizing={"mode": "ratio", "order_size_ratio": 0.1}),
        )
        monkeypatch.setattr(mod, "strategy_gate_v2", lambda **kwargs: StrategyGateResult(allowed=True, reasons=[]))
        monkeypatch.setattr(
            mod,
            "risk_gate",
            lambda ctx: RiskAllowance(allow_open=True, allow_add=True, allow_reduce=True, allow_exit=True, reasons=[]),
        )
        monkeypatch.setattr(
            mod,
            "build_execution_plan",
            lambda **kwargs: ExecutionPlan(
                action="add",
                direction="long",
                allowance=kwargs["allowance"],
                confidence=Confidence(level="high", score=0.9),
                sizing={"mode": "ratio", "order_size_ratio": 0.1},
                notes="traceability-ok",
            ),
        )

        recorder = _Recorder()
        wf = TradeEventWorkflow(
            market_state=_InProcessMarketStateProvider(),
            position_context=_PositionProvider(),
            active_events=_ActiveEventsFromSelectedProvider(),
            recorder=recorder,
        )
        event_id = "evt-trace-001"
        await wf.run(
            TradeEventInput(
                event_id=event_id,
                exchange="binance",
                symbol="ETHUSDT",
                signal_direction="long",
                payload={"event_type": "onchain_alert", "source": "event_center_new"},
            )
        )

        trace = recorder.get_agent_payload(event_id, "decision_trace")
        assert trace
        # signal source 可追溯
        assert ((trace.get("event") or {}).get("payload") or {}).get("source") == "event_center_new"
        # state evidence 可追溯（来自 selected_event_provider）
        assert int((trace.get("evidence") or {}).get("selected_events_count") or 0) >= 1
        # active_events 证据可追溯（来自 selected_event -> normalize）
        features = list(((trace.get("key_features") or {}).get("features") or []))
        active_events_item = next((x for x in features if str((x or {}).get("name") or "") == "active_events_top"), {})
        active_events_value = list((active_events_item or {}).get("value") or [])
        assert active_events_value
        first_event = dict(active_events_value[0] or {})
        assert first_event.get("source") == "event_center_new"
        assert first_event.get("type") == "onchain_alert"
        assert first_event.get("direction") == "bullish"

    import pytest

    monkeypatch = pytest.MonkeyPatch()
    try:
        asyncio.run(_run(monkeypatch))
    finally:
        monkeypatch.undo()
