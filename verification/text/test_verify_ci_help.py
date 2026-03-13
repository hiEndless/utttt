from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run_help(script: str) -> str:
    proc = subprocess.run(
        ["bash", script, "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    return str(proc.stdout or "")


def test_verify_regression_help_contains_pipeline_semantic_terms_guard() -> None:
    out = _run_help("tools/ci/verify_regression.sh")
    assert "Usage:" in out
    assert "pipeline semantic terms doc guard" in out
    assert "MAX_AGENT_READYZ_LEVEL" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out


def test_verify_nightly_help_contains_legacy_confidence_env() -> None:
    out = _run_help("tools/ci/verify_nightly.sh")
    assert "Usage:" in out
    assert "MAX_LEGACY_CONFIDENCE_RATIO" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out


def test_verify_quick_help_contains_optional_agent_readyz_env() -> None:
    out = _run_help("tools/ci/verify_quick.sh")
    assert "Usage:" in out
    assert "WITH_AGENT_READYZ=1" in out
    assert "WITH_PIPELINE_MODE_REPORT=1" in out
    assert "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS" in out
    assert "MAX_PIPELINE_MODE_UNKNOWN_COUNT" in out


def test_verify_local_quick_help_contains_agent_readyz_options() -> None:
    out = _run_help("tools/local/verify_quick.sh")
    assert "Usage:" in out
    assert "--with-agent-readyz" in out
