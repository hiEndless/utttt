from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict

from services.agent_server_new.ports.event_recorder import EventRecorder


class JsonlEventRecorder(EventRecorder):
    """Write market context and agent outputs into a JSONL file."""

    def __init__(self, *, file_path: str) -> None:
        self._file_path = str(file_path or "").strip()
        if not self._file_path:
            raise ValueError("event recorder file_path is required")
        self._lock = threading.Lock()
        Path(self._file_path).parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "JsonlEventRecorder":
        path = str(
            os.getenv("AGENT_EVENT_RECORDER_JSONL_PATH", "verification/reports/agent_server_new_events.jsonl")
            or "verification/reports/agent_server_new_events.jsonl"
        ).strip()
        return cls(file_path=path)

    async def record_market_context(self, event_id: str, payload: Dict[str, Any]) -> None:
        await asyncio.to_thread(
            self._write_line,
            {
                "record_type": "market_context",
                "event_id": str(event_id),
                "payload": dict(payload or {}),
            },
        )

    async def record_agent_output(self, event_id: str, agent_name: str, payload: Dict[str, Any]) -> None:
        await asyncio.to_thread(
            self._write_line,
            {
                "record_type": "agent_output",
                "event_id": str(event_id),
                "agent_name": str(agent_name),
                "payload": dict(payload or {}),
            },
        )

    def _write_line(self, body: Dict[str, Any]) -> None:
        line = {
            "ts_ms": int(time.time() * 1000),
            **dict(body or {}),
        }
        raw = json.dumps(line, ensure_ascii=False)
        with self._lock:
            with open(self._file_path, "a", encoding="utf-8") as f:
                f.write(raw)
                f.write("\n")

