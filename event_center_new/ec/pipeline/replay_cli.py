from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any, Protocol

from .replay import build_default_replay_tool, diff_selected


class RedisRangeClient(Protocol):
    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None):  # noqa: A002, ANN201
        ...


def load_payloads_by_window(
    client: RedisRangeClient,
    *,
    stream: str,
    start_ms: int,
    end_ms: int,
    batch_size: int = 1000,
) -> list[dict[str, Any]]:
    min_id = f"{int(start_ms)}-0"
    max_id = f"{int(end_ms)}-999999"
    entries = client.xrange(stream, min=min_id, max=max_id, count=batch_size) or []
    payloads: list[dict[str, Any]] = []
    for _entry_id, fields in entries:
        raw = fields.get("payload")
        if not isinstance(raw, str):
            continue
        try:
            payloads.append(json.loads(raw))
        except Exception:
            continue
    return payloads


def run_replay_report(
    client: RedisRangeClient,
    *,
    start_ms: int,
    end_ms: int,
    raw_stream: str = "ec:raw",
    selected_stream: str = "ec:selected",
) -> dict[str, Any]:
    raw_events = load_payloads_by_window(
        client,
        stream=raw_stream,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    selected_online = load_payloads_by_window(
        client,
        stream=selected_stream,
        start_ms=start_ms,
        end_ms=end_ms,
    )
    tool = build_default_replay_tool()
    replay = tool.replay_from_dicts(raw_events)
    diffs = diff_selected(replay.selected, selected_online)
    return {
        "start_ms": int(start_ms),
        "end_ms": int(end_ms),
        "streams": {
            "raw": raw_stream,
            "selected": selected_stream,
        },
        "counts": {
            "raw_events": len(raw_events),
            "online_selected": len(selected_online),
            "replay_selected": replay.selected_count,
            "replay_layers": {
                "raw": replay.raw_count,
                "normalized": replay.normalized_count,
                "evidence": replay.evidence_count,
                "context": replay.context_count,
                "selected": replay.selected_count,
            },
        },
        "ok": len(diffs) == 0,
        "diffs": diffs,
        "replay_selected": replay.selected,
        "online_selected": selected_online,
    }


def format_report(report: dict[str, Any], *, pretty: bool = True) -> str:
    if pretty:
        return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(report, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def event_dict_to_stream_fields(payload: dict[str, Any]) -> dict[str, str]:
    """测试辅助：把 payload 转成 Redis stream fields。"""

    return {
        "payload": json.dumps(payload, ensure_ascii=False),
        "ts_ms": str(payload.get("ts_ms", "")),
    }


def replay_result_to_dict(report: dict[str, Any]) -> dict[str, Any]:
    return asdict(report) if hasattr(report, "__dataclass_fields__") else dict(report)
