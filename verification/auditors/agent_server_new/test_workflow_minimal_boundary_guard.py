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
        "horizon_policy_config",
        "resolve_intent",
        "build_rule_plan",
        "strategy_gate_v2",
        "risk_gate",
        "build_execution_plan",
    ]
    for token in forbidden_tokens:
        assert token not in text


def test_trade_event_workflow_no_legacy_module_import() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "app" / "workflows" / "trade_event_workflow.py"
    text = path.read_text(encoding="utf-8")
    forbidden_import_tokens = [
        "domain.intent_resolver",
        "domain.rule_planner",
        "domain.strategy_gate",
        "domain.risk_gate",
        "domain.execution_planner",
        "domain.horizon_policy_gate",
    ]
    for token in forbidden_import_tokens:
        assert token not in text


def test_legacy_domain_modules_removed() -> None:
    root = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "domain"
    legacy_files = [
        "intent_resolver.py",
        "rule_planner.py",
        "strategy_gate.py",
        "strategy_gate_reasons.py",
        "risk_gate.py",
        "risk_gate_reasons.py",
        "horizon_policy_gate.py",
        "horizon_policy_reasons.py",
        "execution_planner.py",
    ]
    for name in legacy_files:
        assert not (root / name).exists()


def test_contracts_no_legacy_intent_rule_types() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "domain" / "contracts.py"
    text = path.read_text(encoding="utf-8")
    assert "ActionIntentType" not in text
    assert "class ActionIntent" not in text
    assert "class RulePlan" not in text
