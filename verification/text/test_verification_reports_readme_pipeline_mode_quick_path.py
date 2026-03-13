from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_verification_reports_readme_contains_pipeline_mode_quick_paths() -> None:
    readme_path = PROJECT_ROOT / "verification" / "reports" / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    assert "bash tools/local/verify_quick.sh --with-pipeline-mode-report" in text
    assert "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz" in text
