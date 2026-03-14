from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_execution_direction_intent_residual_report.sh"


def test_run_execution_direction_intent_residual_report_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--input <path>" in out
    assert "--output <path>" in out
    assert "--limit <n>" in out


def test_run_execution_direction_intent_residual_report_aggregate(tmp_path: Path) -> None:
    input_path = tmp_path / "execution_results.jsonl"
    out_path = tmp_path / "execution_direction_report.json"
    rows = [
        {"decision_id": "dec-1", "direction_intent": "neutral"},
        {"decision_id": "dec-2", "order_result": {"direction_intent": "none"}},
        {"event_id": "evt-3", "payload": {"order_result": {"direction_intent": "long"}}},
    ]
    input_path.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")

    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--input", str(input_path), "--output", str(out_path), "--limit", "10"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_path.exists()

    report = json.loads(out_path.read_text(encoding="utf-8"))
    summary = dict(report.get("summary") or {})
    assert report.get("schema_version") == "execution-direction-intent-residual-report-v1"
    assert summary.get("record_count") == 3
    assert summary.get("direction_intent_total") == 3
    assert summary.get("neutral_count") == 1
    assert summary.get("noncanonical_none_count") == 1
    assert summary.get("long_count") == 1
    assert summary.get("short_count") == 0
    assert summary.get("recommend_action") == "migrate_noncanonical_none_producers"
    examples = list(report.get("noncanonical_none_examples") or [])
    assert len(examples) == 1
    assert examples[0]["path"].endswith("order_result.direction_intent")
