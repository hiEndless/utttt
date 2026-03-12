from __future__ import annotations

RISK_GATE_REASON_DEFAULT_NORMAL = "default_normal"
RISK_GATE_REASON_POSITION_COOLDOWN_ACTIVE = "position_cooldown_active"
RISK_GATE_REASON_MSL_MARKET_FRAGILITY_HIGH = "msl_market_fragility_high"
RISK_GATE_REASON_MSL_MARKET_FRAGILITY_MEDIUM = "msl_market_fragility_medium"
RISK_GATE_REASON_MSL_VOLATILITY_REGIME_HIGH = "msl_volatility_regime_high"
RISK_GATE_REASON_MSL_HORIZON_ALIGNMENT_CONFLICT = "msl_horizon_alignment_conflict"

_PORTFOLIO_RISK_STATE_PREFIX = "portfolio_risk_state_"
_ACTIVE_EVENT_PREFIX = "active_event_"

RISK_GATE_PORTFOLIO_RISK_STATES = ("frozen", "reduce_only", "warn")
RISK_GATE_ACTIVE_EVENT_CRITICAL_TYPES = ("liquidation_cluster", "forced_liquidation", "exchange_risk")
RISK_GATE_ACTIVE_EVENT_ELEVATED_TYPES = ("volatility_spike", "funding_extreme", "basis_dislocation")


def risk_gate_reason_portfolio_risk_state(state: str) -> str:
    s = str(state or "").strip().lower()
    if s not in RISK_GATE_PORTFOLIO_RISK_STATES:
        return f"{_PORTFOLIO_RISK_STATE_PREFIX}unknown"
    return f"{_PORTFOLIO_RISK_STATE_PREFIX}{s}"


def risk_gate_reason_active_event(evt_type: str, severity: str) -> str:
    t = str(evt_type or "").strip().lower()
    sev = str(severity or "").strip().lower()
    if sev not in {"critical", "elevated"}:
        sev = "elevated"
    return f"{_ACTIVE_EVENT_PREFIX}{t}_{sev}"


RISK_GATE_REASON_CODES = (
    RISK_GATE_REASON_DEFAULT_NORMAL,
    RISK_GATE_REASON_POSITION_COOLDOWN_ACTIVE,
    RISK_GATE_REASON_MSL_MARKET_FRAGILITY_HIGH,
    RISK_GATE_REASON_MSL_MARKET_FRAGILITY_MEDIUM,
    RISK_GATE_REASON_MSL_VOLATILITY_REGIME_HIGH,
    RISK_GATE_REASON_MSL_HORIZON_ALIGNMENT_CONFLICT,
    *(risk_gate_reason_portfolio_risk_state(x) for x in RISK_GATE_PORTFOLIO_RISK_STATES),
    *(risk_gate_reason_active_event(x, "critical") for x in RISK_GATE_ACTIVE_EVENT_CRITICAL_TYPES),
    *(risk_gate_reason_active_event(x, "elevated") for x in RISK_GATE_ACTIVE_EVENT_ELEVATED_TYPES),
)

