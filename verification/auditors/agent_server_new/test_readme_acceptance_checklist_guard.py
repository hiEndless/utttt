import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_readme_has_frozen_main_flow_acceptance_checklist() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "## 当前主链路验收清单" in text
    assert "SignalEvaluator -> SignalRouter -> SignalDecisionAgent -> ExecutionPlan" in text
    assert "DecisionTrace.routing.pipeline_mode" in text
    assert "ExecutionPlan.sizing/allowance" in text
    assert "execution_service" in text
    assert "唯一权威" in text
    assert "这只是过渡方案" not in text
    assert "还需要继续收窄" not in text
    assert "## 架构收敛清单" in text
    assert "### 已完成项" in text
    assert "### 待优化项" in text
    assert "### 第一阶段：逻辑剥离" not in text
    assert "### 第二阶段：依赖反转" not in text
    assert "### 第三阶段：物理拆分" not in text
