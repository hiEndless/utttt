import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_refactor_plan_uses_completed_status_language() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "REFACTOR_PLAN_V2.md"
    text = path.read_text(encoding="utf-8")
    assert "已完成状态清单（替代 Phase C/Phase D）" in text
    assert "不再提供 legacy/minimal 双态切换" in text
    assert "不保留兼容壳 workflow" in text
    assert "Phase C（兼容阶段）" not in text
    assert "Phase D（收口阶段）" not in text
    assert "当前进展补充（已完成能力矩阵）" in text
    assert "| 能力域 | 已完成能力 | 关键锚点 |" in text


def test_codex_task_tree_no_compat_fallback_language() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "CODEX_TASK_TREE.md"
    text = path.read_text(encoding="utf-8")
    assert "compat 作为可选 fallback" not in text
    assert "stub 仅作为 fallback" not in text
    assert "不允许新增 compat/fallback 回退壳" in text
