from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_feature_contract_guard_wires_feature_docs_source_names_guard() -> None:
    text = _read("tools/local/check_feature_contract_guard.sh")
    assert "bash tools/local/check_feature_docs_source_names_guard.sh" in text


def test_verify_quick_wires_feature_docs_source_names_guard() -> None:
    text = _read("tools/ci/verify_quick.sh")
    assert "bash tools/local/check_feature_docs_source_names_guard.sh" in text
