import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_trade_event_workflow_no_legacy_gate_dependency() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "app" / "workflows" / "trade_event_workflow.py"
    text = path.read_text(encoding="utf-8")
    forbidden_tokens = [
        "legacy_pipeline_enabled",
        "resolve_intent",
        "build_rule_plan",
        "strategy_gate_v2",
        "risk_gate",
        "build_execution_plan",
    ]
    for token in forbidden_tokens:
        assert token not in text
