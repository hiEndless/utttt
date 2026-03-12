from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from verification.reports.check_thresholds import main


def test_check_thresholds_passes_when_legacy_ratio_within_limit(tmp_path: Path) -> None:
    summary = {
        "report_count": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "semantic_error_count": 0,
        "semantic_warning_count": 0,
        "execution_legacy_confidence_usage_ratio": 0.1,
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    code = main(
        [
            "--summary",
            str(path),
            "--min-pass-rate",
            "1.0",
            "--max-failed",
            "0",
            "--min-reports",
            "1",
            "--max-semantic-errors",
            "0",
            "--max-legacy-confidence-ratio",
            "0.2",
        ]
    )
    assert code == 0


def test_check_thresholds_fails_when_legacy_ratio_exceeds_limit(tmp_path: Path) -> None:
    summary = {
        "report_count": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "semantic_error_count": 0,
        "semantic_warning_count": 0,
        "execution_legacy_confidence_usage_ratio": 0.3,
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    code = main(
        [
            "--summary",
            str(path),
            "--min-pass-rate",
            "1.0",
            "--max-failed",
            "0",
            "--min-reports",
            "1",
            "--max-semantic-errors",
            "0",
            "--max-legacy-confidence-ratio",
            "0.2",
        ]
    )
    assert code == 1


def test_check_thresholds_fails_when_agent_readyz_level_exceeds_limit(tmp_path: Path) -> None:
    summary = {
        "report_count": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "semantic_error_count": 0,
        "semantic_warning_count": 0,
        "execution_legacy_confidence_usage_ratio": 0.0,
        "agent_readyz_report_count": 1,
        "agent_readyz_status_level": "red",
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    code = main(
        [
            "--summary",
            str(path),
            "--max-agent-readyz-level",
            "yellow",
        ]
    )
    assert code == 1


def test_check_thresholds_fails_when_require_agent_readyz_report_but_missing(tmp_path: Path) -> None:
    summary = {
        "report_count": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "semantic_error_count": 0,
        "semantic_warning_count": 0,
        "execution_legacy_confidence_usage_ratio": 0.0,
        "agent_readyz_report_count": 0,
    }
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    code = main(
        [
            "--summary",
            str(path),
            "--require-agent-readyz-report",
        ]
    )
    assert code == 1
