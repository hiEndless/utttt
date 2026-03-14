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
    assert "执行信号语义判定（accept/reject/uncertain）" in text
    assert "消费 `signal_event`" in text
    assert "消费 `active_events`" in text
    assert "消费 `MSL`" in text
    assert "执行信号评估与事件路由" in text
    assert "该对象是 agent 语义输出，不等价于 execution 最终动作" in text
    assert "做 signal semantic decision（accept/reject/uncertain）" not in text
    assert "consume `signal_event`" not in text
    assert "consume `active_events`" not in text
    assert "consume `MSL`" not in text
    assert "### 本地灰度观测最短命令" not in text
    assert "灰度推进阶段" not in text
    assert "### 本地常态观测最短命令" in text
