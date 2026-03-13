from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.text.readme_contracts import (
    README_CONTRACTS_DOCS_REQUIRED_SNIPPETS,
    README_CONTRACTS_DOC_LABELS,
    README_CONTRACTS_SNIPPETS_DOCS,
    README_CONTRACTS_VERSION,
)


@pytest.mark.parametrize("readme_relpath", [str(p) for p in README_CONTRACTS_SNIPPETS_DOCS])
def test_readme_contains_pipeline_mode_quick_paths(readme_relpath: str) -> None:
    readme_path = PROJECT_ROOT / readme_relpath
    text = readme_path.read_text(encoding="utf-8")
    required_snippets = README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.get(Path(readme_relpath), ())
    for snippet in required_snippets:
        label = README_CONTRACTS_DOC_LABELS.get(Path(readme_relpath), readme_relpath)
        assert snippet in text, f"[{README_CONTRACTS_VERSION}] missing snippet in {label}: {snippet}"


def test_readme_snippet_overrides_reference_known_docs() -> None:
    allowed = {Path(p) for p in README_CONTRACTS_SNIPPETS_DOCS}
    required_paths = set(README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.keys())
    assert required_paths.issubset(allowed), f"required docs not registered: {required_paths - allowed}"


def test_readme_contracts_doc_list_is_sorted() -> None:
    doc_list = [str(p) for p in README_CONTRACTS_SNIPPETS_DOCS]
    assert doc_list == sorted(doc_list), f"README_CONTRACTS_SNIPPETS_DOCS not sorted: {doc_list}"


def test_readme_contracts_docs_exist() -> None:
    for relpath in README_CONTRACTS_SNIPPETS_DOCS:
        full_path = PROJECT_ROOT / relpath
        label = README_CONTRACTS_DOC_LABELS.get(relpath, relpath)
        assert full_path.is_file(), f"missing readme file: {label}"


def test_readme_contract_labels_cover_all_docs() -> None:
    docs = set(README_CONTRACTS_SNIPPETS_DOCS)
    labels = set(README_CONTRACTS_DOC_LABELS.keys())
    assert labels.issuperset(docs), f"missing labels for docs: {docs - labels}"


def test_readme_snippet_overrides_are_sorted() -> None:
    required_list = [str(p) for p in README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.keys()]
    assert required_list == sorted(required_list), f"README_CONTRACTS_DOCS_REQUIRED_SNIPPETS not sorted: {required_list}"


def test_readme_snippet_override_values_are_sorted() -> None:
    for path, snippets in README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.items():
        ordered = list(snippets)
        assert ordered == sorted(ordered), f"override snippets not sorted for {path}: {ordered}"


def test_pipeline_mode_snippets_are_sorted() -> None:
    for path, snippets in README_CONTRACTS_DOCS_REQUIRED_SNIPPETS.items():
        for snippet in snippets:
            assert snippet, f"empty snippet in {path}"
