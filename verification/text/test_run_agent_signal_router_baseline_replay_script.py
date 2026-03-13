from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_signal_router_baseline_replay.sh"


def test_run_agent_signal_router_baseline_replay_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--samples <path>" in out
    assert "--format <type>" in out
    assert "--strict <0|1>" in out


def test_run_agent_signal_router_baseline_replay_json_output(tmp_path: Path) -> None:
    samples_path = tmp_path / "samples.json"
    out_path = tmp_path / "replay.latest.json"
    samples_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "case-1",
                    "payload": {"selected_type": "market_indicator_signal"},
                    "expected_agent_key": "technical",
                    "expected_normalized_event_type": "market_indicator_signal",
                    "expected_match_mode": "canonical_or_raw",
                },
                {
                    "case_id": "case-2",
                    "payload": {"event_type": "chain_wallet_anomaly"},
                    "expected_agent_key": "onchain",
                    "expected_normalized_event_type": "onchain_wallet_anomaly",
                    "expected_match_mode": "alias",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--samples",
            str(samples_path),
            "--format",
            "json",
            "--output",
            str(out_path),
            "--strict",
            "1",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert out_path.exists()
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "agent-signal-router-baseline-replay-v1"
    assert report["ok"] is True
    rows = list(report["rows"])
    assert len(rows) == 2
    assert rows[0]["passed"] is True
    assert rows[1]["passed"] is True


def test_run_agent_signal_router_baseline_replay_strict_fail(tmp_path: Path) -> None:
    samples_path = tmp_path / "samples.bad.json"
    samples_path.write_text(
        json.dumps(
            [
                {
                    "case_id": "bad-case",
                    "payload": {"event_type": "chain_wallet_anomaly"},
                    "expected_agent_key": "technical",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--samples",
            str(samples_path),
            "--strict",
            "1",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
