from __future__ import annotations

import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def test_verify_report_aggregate_help_contains_decision_trace_schema_guard_flags() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/verify_report_aggregate.sh", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--with-decision-trace-schema-guard" in out
    assert "--decision-trace-schema-guard-path <path>" in out
    assert "--with-pipeline-mode-report" in out
    assert "--pipeline-mode-report-path <path>" in out
    assert "--with-event-type-match-report" in out
    assert "--event-type-match-report-path <path>" in out


def test_aggregate_and_check_help_contains_decision_trace_schema_guard_flags() -> None:
    proc = subprocess.run(
        ["bash", "tools/local/aggregate_and_check.sh", "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--with-decision-trace-schema-guard" in out
    assert "--decision-trace-schema-guard-path <path>" in out
    assert "--with-pipeline-mode-report" in out
    assert "--pipeline-mode-report-path <path>" in out
    assert "--with-event-type-match-report" in out
    assert "--event-type-match-report-path <path>" in out
