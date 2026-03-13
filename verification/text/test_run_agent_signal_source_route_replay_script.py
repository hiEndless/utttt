from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCRIPT_PATH = PROJECT_ROOT / "tools" / "local" / "run_agent_signal_source_route_replay.sh"


def test_run_agent_signal_source_route_replay_help() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH), "--help"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "--exchange <name>" in out
    assert "--symbol <name>" in out
    assert "--format <type>" in out
    assert "--output <path>" in out
    assert "signal_source_type -> decision_agent_key -> execution_action" in out


def test_run_agent_signal_source_route_replay_output_table() -> None:
    proc = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    out = str(proc.stdout or "")
    assert "event_id\tsignal_source_type\texpected_agent_key\tdecision_agent_key\t" in out
    assert "market_indicator\ttechnical\ttechnical" in out
    assert "onchain_wallet\tonchain\tonchain" in out
    assert "large_liquidation\tliquidation\tliquidation" in out
    assert "social_news\tsocial_news\tsocial_news" in out


def test_run_agent_signal_source_route_replay_output_json_and_output_file(tmp_path: Path) -> None:
    out_path = tmp_path / "route_replay.latest.json"
    proc = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--format",
            "json",
            "--output",
            str(out_path),
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    lines = [x.strip() for x in str(proc.stdout or "").splitlines() if x.strip()]
    assert lines
    assert lines[0].startswith("[ok] wrote ")
    payload = json.loads(lines[-1])
    assert payload["schema_version"] == "agent-signal-source-route-replay-v1"
    assert payload["ok"] is True
    rows = list(payload.get("rows") or [])
    assert len(rows) == 4
    by_source = {str(x.get("signal_source_type")): x for x in rows}
    assert by_source["market_indicator"]["decision_agent_key"] == "technical"
    assert by_source["onchain_wallet"]["decision_agent_key"] == "onchain"
    assert by_source["large_liquidation"]["decision_agent_key"] == "liquidation"
    assert by_source["social_news"]["decision_agent_key"] == "social_news"
    assert all(bool(x.get("route_match")) for x in rows)
    assert out_path.exists()
