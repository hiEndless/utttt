from __future__ import annotations

import asyncio
import datetime
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict

from services.agent_server_new.ports.event_recorder import EventRecorder


class JsonlEventRecorder(EventRecorder):
    """Write market context and agent outputs into a JSONL file."""

    def __init__(
        self,
        *,
        file_path: str,
        rotate_daily: bool = True,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._file_path = str(file_path or "").strip()
        if not self._file_path:
            raise ValueError("event recorder file_path is required")
        self._rotate_daily = bool(rotate_daily)
        self._max_bytes = max(0, int(max_bytes))
        self._lock = threading.Lock()
        Path(self._file_path).parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "JsonlEventRecorder":
        path = str(
            os.getenv("AGENT_EVENT_RECORDER_JSONL_PATH", "verification/reports/agent_server_new_events.jsonl")
            or "verification/reports/agent_server_new_events.jsonl"
        ).strip()
        rotate_daily = str(os.getenv("AGENT_EVENT_RECORDER_ROTATE_DAILY", "true") or "true").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        max_bytes_raw = str(os.getenv("AGENT_EVENT_RECORDER_MAX_BYTES", str(10 * 1024 * 1024)) or str(10 * 1024 * 1024)).strip()
        try:
            max_bytes = max(0, int(max_bytes_raw))
        except Exception:
            max_bytes = 10 * 1024 * 1024
        return cls(file_path=path, rotate_daily=rotate_daily, max_bytes=max_bytes)

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
            target_path = self._resolve_target_path()
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(raw)
                f.write("\n")

    def _resolve_target_path(self) -> str:
        base = Path(self._file_path)
        target = base
        if self._rotate_daily:
            day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
            target = self._with_suffix(base, day)
        if self._max_bytes <= 0:
            return str(target)
        if (not target.exists()) or target.stat().st_size < self._max_bytes:
            return str(target)
        idx = 1
        while True:
            candidate = self._with_suffix(target, str(idx))
            if (not candidate.exists()) or candidate.stat().st_size < self._max_bytes:
                return str(candidate)
            idx += 1

    @staticmethod
    def _with_suffix(path: Path, suffix: str) -> Path:
        if path.suffix:
            return path.with_name(f"{path.stem}.{suffix}{path.suffix}")
        return path.with_name(f"{path.name}.{suffix}")
