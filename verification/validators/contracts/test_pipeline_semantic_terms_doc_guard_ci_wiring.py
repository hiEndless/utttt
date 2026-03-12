from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_verify_regression_wires_pipeline_semantic_terms_doc_guard() -> None:
    text = _read("tools/ci/verify_regression.sh")
    assert "bash tools/local/check_pipeline_semantic_terms_doc_guard.sh" in text


def test_verify_nightly_wires_pipeline_semantic_terms_doc_guard() -> None:
    text = _read("tools/ci/verify_nightly.sh")
    assert "bash tools/local/check_pipeline_semantic_terms_doc_guard.sh" in text

