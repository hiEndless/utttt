from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.agent_server_new.adapters.event_recorder_jsonl import JsonlEventRecorder


def test_jsonl_event_recorder_writes_market_context_and_agent_output(tmp_path) -> None:
    file_path = tmp_path / "agent_events.jsonl"
    recorder = JsonlEventRecorder(file_path=str(file_path))

    import asyncio

    async def _run() -> None:
        await recorder.record_market_context("evt-1", {"symbol": "ETHUSDT"})
        await recorder.record_agent_output("evt-1", "signal_evaluator", {"verdict": "accept"})

    asyncio.run(_run())

    lines = file_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["record_type"] == "market_context"
    assert second["record_type"] == "agent_output"
    assert second["agent_name"] == "signal_evaluator"

