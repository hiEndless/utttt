import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.domain.horizon_policy_gate import horizon_policy_gate, load_horizon_policy_config_from_env


def test_horizon_policy_gate_blocks_increase_on_wait_confirmation():
    out = horizon_policy_gate(
        suggested_policy="wait_confirmation",
        policy_reason="short_long_trend_conflict",
        intent="increase",
    )
    assert out.allowed is False
    assert "horizon_policy_wait_confirmation" in list(out.reasons or [])


def test_horizon_policy_gate_blocks_increase_on_reduce_risk():
    out = horizon_policy_gate(
        suggested_policy="reduce_risk",
        policy_reason="timeframe_mixed",
        intent="increase",
    )
    assert out.allowed is False
    assert "horizon_policy_reduce_risk" in list(out.reasons or [])


def test_horizon_policy_gate_allows_non_increase():
    out = horizon_policy_gate(
        suggested_policy="wait_confirmation",
        policy_reason="short_long_trend_conflict",
        intent="hold",
    )
    assert out.allowed is True


def test_horizon_policy_gate_respects_custom_config():
    out = horizon_policy_gate(
        suggested_policy="wait_confirmation",
        policy_reason="short_long_trend_conflict",
        intent="increase",
        config={"block_on_increase_policies": ["reduce_risk"]},
    )
    assert out.allowed is True


def test_load_horizon_policy_config_from_env_csv(monkeypatch):
    monkeypatch.setenv("AGENT_HORIZON_POLICY_BLOCK_ON_INCREASE", "reduce_risk")
    cfg = load_horizon_policy_config_from_env()
    assert cfg["block_on_increase_policies"] == ["reduce_risk"]


def test_load_horizon_policy_config_from_env_json(monkeypatch):
    monkeypatch.setenv("AGENT_HORIZON_POLICY_CONFIG_JSON", '{"block_on_increase_policies":["wait_confirmation"]}')
    cfg = load_horizon_policy_config_from_env()
    assert cfg["block_on_increase_policies"] == ["wait_confirmation"]
