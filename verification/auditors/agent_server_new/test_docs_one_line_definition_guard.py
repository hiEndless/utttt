import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


_ONE_LINE_DEFINITION = "agent 只回答“这个信号是否可信”，execution 才回答“是否允许执行以及如何执行”。"


def test_one_line_definition_is_consistent_between_readme_and_refactor_plan() -> None:
    readme = (Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md").read_text(encoding="utf-8")
    plan = (Path(PROJECT_ROOT) / "services" / "agent_server_new" / "docs" / "REFACTOR_PLAN_V2.md").read_text(
        encoding="utf-8"
    )
    assert _ONE_LINE_DEFINITION in readme
    assert _ONE_LINE_DEFINITION in plan
