from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_docs_contracts_bundle_wires_pipeline_semantic_terms_doc_guard() -> None:
    text = _read("tools/local/check_docs_contracts_bundle.sh")
    assert "bash tools/local/check_pipeline_semantic_terms_doc_guard.sh" in text

