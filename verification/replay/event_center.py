from __future__ import annotations

from typing import Any, Dict, List

from services.event_center_new.ec.pipeline.replay_cli import format_report, run_replay_report


def run_event_center_replay_report(
    client: Any,
    *,
    start_ms: int,
    end_ms: int,
    raw_stream: str = "ec:raw",
    selected_stream: str = "ec:selected",
    ignore_fields: List[str] | None = None,
) -> Dict[str, Any]:
    return run_replay_report(
        client,
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        raw_stream=str(raw_stream),
        selected_stream=str(selected_stream),
        ignore_fields=list(ignore_fields or []),
    )


def render_event_center_replay_report(report: Dict[str, Any], *, pretty: bool = True) -> str:
    return format_report(dict(report or {}), pretty=bool(pretty))
