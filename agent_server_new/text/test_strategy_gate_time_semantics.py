from __future__ import annotations

import datetime
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent_server_new.domain.contracts import ActionIntent, Confidence, RulePlan, SignalVerdict
from agent_server_new.domain.strategy_gate import _extract_signal_event_ts_ms, strategy_gate_v2
from market_state_engine.contracts import (
    KeyLevels,
    LiquidityState,
    MarketRegime,
    MarketStateMSL,
    PositioningState,
    RiskState,
    StructureState,
    VolatilityState,
)


def _sample_msl(ts_ms: int) -> MarketStateMSL:
    ts_iso = datetime.datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return MarketStateMSL(
        version=2,
        timestamp=ts_iso,
        symbol="ETHUSDT",
        market_regime=MarketRegime(trend="bullish", phase="continuation", timeframe_alignment="aligned", strength=0.7),
        liquidity=LiquidityState(
            dominant_pressure="buyers",
            liquidity_risk="neutral",
            orderbook_bias="neutral",
            liquidation_proximity="none",
        ),
        positioning=PositioningState(crowding="balanced", whale_bias="neutral", retail_bias="neutral", oi_trend="flat"),
        volatility=VolatilityState(volatility_regime="normal", expansion_risk="unknown", volatility_direction="neutral"),
        risk=RiskState(cascade_risk="low", squeeze_probability="low", reversal_risk="low"),
        market_structure=StructureState(
            support_strength="unknown",
            resistance_strength="unknown",
            range_state="breakout",
            trend_structure="hh_hl",
        ),
        key_levels=KeyLevels(),
        anomalies=[],
        summary="ok",
    )


def _sample_inputs() -> tuple[SignalVerdict, ActionIntent, RulePlan]:
    signal = SignalVerdict(direction="long", verdict="accept", confidence=Confidence(level="medium", score=0.7))
    intent = ActionIntent(intent="increase", direction="long", confidence=Confidence(level="medium", score=0.7))
    rule_plan = RulePlan(intent=intent, sizing={"mode": "ratio", "order_size_ratio": 0.1})
    return signal, intent, rule_plan


def test_extract_signal_event_ts_ms_prefers_explicit_ts_ms() -> None:
    out = _extract_signal_event_ts_ms(
        {
            "ts_ms": 1700000000123,
            "timestamp_ms": 1700000000456,
            "ts": 1700000000789,
            "timestamp": "2026-03-09T12:00:00Z",
        }
    )
    assert out == 1700000000123


def test_extract_signal_event_ts_ms_supports_iso_timestamp() -> None:
    out = _extract_signal_event_ts_ms({"timestamp": "2026-03-09T12:00:00Z"})
    assert isinstance(out, int)
    assert out and out > 0


def test_strategy_gate_v2_marks_stale_when_iso_timestamp_old() -> None:
    msl = _sample_msl(1_760_000_000_000)
    signal, intent, rule_plan = _sample_inputs()
    out = strategy_gate_v2(
        msl=msl,
        signal=signal,
        intent=intent,
        rule_plan=rule_plan,
        position_context={},
        signal_event={"timestamp": "2025-01-01T00:00:00Z"},
    )
    assert out.allowed is False
    assert "signal_stale" in list(out.reasons or [])
