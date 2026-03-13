from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_REQUIRED_SNIPPETS = (
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report",
    "bash tools/local/verify_quick.sh --with-pipeline-mode-report --with-agent-readyz",
)


@pytest.mark.parametrize(
    ("readme_relpath", "required_snippets"),
    [
        ("services/agent_server_new/README.md", _REQUIRED_SNIPPETS + ("pipeline_mode_summary",)),
        ("verification/reports/README.md", _REQUIRED_SNIPPETS),
    ],
)
def test_readme_contains_pipeline_mode_quick_paths(readme_relpath: str, required_snippets: tuple[str, ...]) -> None:
    readme_path = PROJECT_ROOT / readme_relpath
    text = readme_path.read_text(encoding="utf-8")
    for snippet in required_snippets:
        assert snippet in text, f"missing snippet in {readme_relpath}: {snippet}"
