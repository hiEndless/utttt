import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_legacy_pipeline_removed_from_bootstrap_env() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "app" / "bootstrap.py"
    text = path.read_text(encoding="utf-8")
    assert "AGENT_LEGACY_PIPELINE_ENABLED" not in text


def test_legacy_pipeline_removed_from_readme() -> None:
    path = Path(PROJECT_ROOT) / "services" / "agent_server_new" / "README.md"
    text = path.read_text(encoding="utf-8")
    assert "AGENT_LEGACY_PIPELINE_ENABLED" not in text
