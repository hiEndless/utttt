from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.risk_gate import RiskGateContext, risk_gate


def test_legacy_risk_gate_context_critical_regime_blocks_add() -> None:
    ctx = RiskGateContext(global_regime="critical", cooldown_active=False)
    out = risk_gate(ctx)
    assert out.allow_add is False
    assert out.allow_open is False
    assert "global_regime_critical" in list(out.reasons or [])


def test_legacy_risk_gate_context_cooldown_blocks_add() -> None:
    ctx = RiskGateContext(global_regime="normal", cooldown_active=True)
    out = risk_gate(ctx)
    assert out.allow_add is False
    assert out.allow_open is False
    assert "global_cooldown_active" in list(out.reasons or [])


def test_legacy_risk_gate_context_normal_allows_add() -> None:
    ctx = RiskGateContext(global_regime="normal", cooldown_active=False)
    out = risk_gate(ctx)
    assert out.allow_add is True
    assert out.allow_open is True
