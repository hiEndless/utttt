from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import (
    PIPELINE_MODE_QUICK_SNIPPETS,
    README_CONTRACTS_SNIPPETS_DOCS,
    README_SNIPPET_OVERRIDES,
    README_CONTRACTS_VERSION,
)


@pytest.mark.parametrize("readme_relpath", [str(p) for p in README_CONTRACTS_SNIPPETS_DOCS])
def test_readme_contains_pipeline_mode_quick_paths(readme_relpath: str) -> None:
    readme_path = PROJECT_ROOT / readme_relpath
    text = readme_path.read_text(encoding="utf-8")
    override = README_SNIPPET_OVERRIDES.get(Path(readme_relpath))
    required_snippets = PIPELINE_MODE_QUICK_SNIPPETS + (override or ())
    for snippet in required_snippets:
        assert snippet in text, f"[{README_CONTRACTS_VERSION}] missing snippet in {readme_relpath}: {snippet}"
