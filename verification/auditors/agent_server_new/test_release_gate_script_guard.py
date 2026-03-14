import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_single_path_release_gate_script_contains_required_checks() -> None:
    path = Path(PROJECT_ROOT) / "tools" / "local" / "check_agent_single_path_release_gate.sh"
    text = path.read_text(encoding="utf-8")
    assert "set -euo pipefail" in text
    assert "/internal/agent/readyz" in text
    assert "/internal/execution/healthz" in text
    assert "--use-execution-result" in text
    assert "AGENT_RUNTIME_PROFILE=prod" in text
    assert "runner output source is not execution" in text


def test_agent_readme_mentions_single_path_release_gate_script() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "check_agent_single_path_release_gate.sh" in text
