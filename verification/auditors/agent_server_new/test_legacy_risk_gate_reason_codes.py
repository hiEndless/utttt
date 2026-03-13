from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.risk_gate_reasons import (
    RISK_GATE_REASON_CODES,
    risk_gate_reason_active_event,
    risk_gate_reason_portfolio_risk_state,
)


def test_legacy_risk_gate_reason_registry_unique() -> None:
    assert len(RISK_GATE_REASON_CODES) == len(set(RISK_GATE_REASON_CODES))


def test_legacy_risk_gate_reason_helpers_are_canonical() -> None:
    assert risk_gate_reason_portfolio_risk_state("warn") in set(RISK_GATE_REASON_CODES)
    assert risk_gate_reason_active_event("forced_liquidation", "critical") in set(RISK_GATE_REASON_CODES)
