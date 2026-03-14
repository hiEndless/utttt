import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_services_readme_uses_agent_server_new_runtime_entrypoints_only() -> None:
    path = Path(PROJECT_ROOT) / "services" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "python -m services.agent_server_new.main" in text
    assert "python -m services.agent_server_new.pipeline_smoke" in text
    assert "python -m services.agent_server_new.memory_summary_runner" in text
    assert "python -m agent_server.main" not in text
    assert "python -m agent_server" not in text


def test_local_agent_wrappers_pin_to_services_agent_server_new() -> None:
    scripts = [
        "tools/local/run_agent_runner.sh",
        "tools/local/run_agent_pipeline_smoke.sh",
        "tools/local/run_agent_memory_summary.sh",
    ]
    for rel in scripts:
        path = Path(PROJECT_ROOT) / rel
        text = path.read_text(encoding="utf-8")
        assert "services.agent_server_new" in text
        assert "agent_server.main" not in text
