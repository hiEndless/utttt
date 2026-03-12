from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def test_verify_quick_wires_alternative_source_single_source_guard() -> None:
    text = _read("tools/ci/verify_quick.sh")
    assert "bash tools/local/check_alternative_source_single_source_guard.sh" in text


def test_new_arch_full_wires_alternative_source_single_source_guard() -> None:
    text = _read("tools/ci/new_arch_guards_full.sh")
    assert "bash tools/local/check_alternative_source_single_source_guard.sh" in text

