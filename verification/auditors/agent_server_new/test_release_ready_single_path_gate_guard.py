import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_release_ready_script_runs_single_path_gate_by_default() -> None:
    path = Path(PROJECT_ROOT) / "tools" / "local" / "check_release_ready.sh"
    text = path.read_text(encoding="utf-8")
    assert 'WITH_AGENT_SINGLE_PATH_RELEASE_GATE="${WITH_AGENT_SINGLE_PATH_RELEASE_GATE:-1}"' in text
    assert "bash tools/local/check_agent_single_path_release_gate.sh" in text
    assert "single_path_release_gate (skip by WITH_AGENT_SINGLE_PATH_RELEASE_GATE=0)" in text
