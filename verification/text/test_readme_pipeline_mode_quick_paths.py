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


def test_readme_snippet_overrides_reference_known_docs() -> None:
    allowed = {Path(p) for p in README_CONTRACTS_SNIPPETS_DOCS}
    override_paths = set(README_SNIPPET_OVERRIDES.keys())
    assert override_paths.issubset(allowed), f"override paths not registered: {override_paths - allowed}"


def test_readme_contracts_doc_list_is_sorted() -> None:
    doc_list = [str(p) for p in README_CONTRACTS_SNIPPETS_DOCS]
    assert doc_list == sorted(doc_list), f"README_CONTRACTS_SNIPPETS_DOCS not sorted: {doc_list}"


def test_readme_snippet_overrides_are_sorted() -> None:
    override_list = [str(p) for p in README_SNIPPET_OVERRIDES.keys()]
    assert override_list == sorted(override_list), f"README_SNIPPET_OVERRIDES not sorted: {override_list}"


def test_readme_snippet_override_values_are_sorted() -> None:
    for path, snippets in README_SNIPPET_OVERRIDES.items():
        ordered = list(snippets)
        assert ordered == sorted(ordered), f"override snippets not sorted for {path}: {ordered}"


def test_pipeline_mode_snippets_are_sorted() -> None:
    ordered = list(PIPELINE_MODE_QUICK_SNIPPETS)
    assert ordered == sorted(ordered), f"PIPELINE_MODE_QUICK_SNIPPETS not sorted: {ordered}"
