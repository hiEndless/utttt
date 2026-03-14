import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_agent_env_example_contains_prod_baseline_keys() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / ".env.example"
    text = path.read_text(encoding="utf-8")
    assert "AGENT_EXECUTION_ENABLED=true" in text
    assert "AGENT_READY_CHECK_EXECUTION_SERVICE=true" in text
    assert "AGENT_READY_CHECK_UPSTREAM_STRICT=true" in text
    assert "AGENT_LEGACY_PIPELINE_ENABLED" not in text


def test_agent_readme_contains_prod_baseline_section() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "## 生产配置基线（唯一链路）" in text
    assert "AGENT_RUNTIME_PROFILE=prod" in text
    assert "AGENT_EXECUTION_ENABLED=true" in text
