import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_readme_freezes_minimal_main_flow_and_historical_flow_label() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "### 当前主链路（冻结）" in text
    assert "SignalEvaluator -> SignalRouter -> SignalDecisionAgent -> ExecutionPlan" in text
    assert "### 历史链路（已下线）" in text
    assert "IntentResolver -> RulePlanner -> HorizonPolicyGate -> StrategyGate -> RiskGate -> ExecutionPlanner" in text
    assert "### 当前实现（过渡态）" not in text
    assert "做 signal semantic decision（accept/reject/uncertain）" in text
    assert "该对象是 agent 语义输出，不等价于 execution 最终动作" in text
    assert "做 intent resolve / rule planning" not in text
    assert "做 strategy gating / risk gating" not in text
