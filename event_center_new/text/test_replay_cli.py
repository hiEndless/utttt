from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sys
import time

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from event_center_new.ec.contracts import EventEnvelope, EventSource
from event_center_new.ec.pipeline.replay import build_default_replay_tool
from event_center_new.ec.pipeline.replay_cli import event_dict_to_stream_fields, run_replay_report


class _FakeRedisRange:
    def __init__(self) -> None:
        self._streams: dict[str, list[tuple[str, dict[str, str]]]] = {}

    def add(self, stream: str, entry_id: str, payload: dict) -> None:
        self._streams.setdefault(stream, []).append((entry_id, event_dict_to_stream_fields(payload)))

    def xrange(self, name: str, min: str = "-", max: str = "+", count: int | None = None):  # noqa: A002, ANN201
        items = list(self._streams.get(name, []))
        min_ms = int(str(min).split("-")[0]) if min != "-" else -1
        max_ms = int(str(max).split("-")[0]) if max != "+" else 10**18
        out = []
        for entry_id, fields in items:
            ms = int(str(entry_id).split("-")[0])
            if min_ms <= ms <= max_ms:
                out.append((entry_id, fields))
        if count is not None:
            out = out[:count]
        return out

    def exists(self, name: str) -> int:
        return 1 if name in self._streams else 0


def _sample_event(ts_ms: int) -> EventEnvelope:
    return EventEnvelope(
        id=f"replay-{ts_ms}",
        ts_ms=ts_ms,
        asset="ETHUSDT",
        kind="tactical",
        type="technical.indicator_signal",
        source=EventSource(name="feature_service", category="technical"),
        importance=0.8,
        ttl_ms=600000,
        payload={
            "evidences": [
                {"type": "a", "direction": "bullish", "strength": 0.7, "horizon": "short", "importance": 0.8},
                {"type": "b", "direction": "bullish", "strength": 0.6, "horizon": "short", "importance": 0.7},
            ]
        },
    )


def test_run_replay_report_ok_when_selected_matches() -> None:
    now_ms = int(time.time() * 1000)
    event = _sample_event(now_ms)
    tool = build_default_replay_tool()
    replay = tool.replay([event])
    fake = _FakeRedisRange()
    fake.add("ec:raw", f"{now_ms}-1", asdict(event))
    for i, item in enumerate(replay.selected, start=1):
        fake.add("ec:selected", f"{now_ms}-{i}", item)

    report = run_replay_report(fake, start_ms=now_ms - 1, end_ms=now_ms + 1)
    assert report["ok"] is True
    assert report["counts"]["raw_events"] == 1
    assert report["counts"]["online_selected"] == report["counts"]["replay_selected"] == 1
    assert report["diffs"] == []
    assert report["signatures"]["online_selected"] == report["signatures"]["replay_selected"]
    assert report["selected_contract"]["ok"] is True
    assert report["selected_contract"]["schema_path"] == "event_center_new/docs/selected_event.schema.json"
    assert "direction_hint" in report["selected_contract"]["required_fields"]


def test_run_replay_report_has_diff_when_selected_mismatch() -> None:
    now_ms = int(time.time() * 1000)
    event = _sample_event(now_ms)
    fake = _FakeRedisRange()
    fake.add("ec:raw", f"{now_ms}-1", asdict(event))
    fake.add(
        "ec:selected",
        f"{now_ms}-1",
        {
            "asset": "ETHUSDT",
            "ts_ms": now_ms,
            "selected_type": "event.selected",
            "direction_hint": "bearish",
            "priority": "low",
            "context_snapshot": {},
            "trigger_event": None,
            "route": {"review_required": True},
        },
    )
    report = run_replay_report(fake, start_ms=now_ms - 1, end_ms=now_ms + 1)
    assert report["ok"] is False
    assert len(report["diffs"]) >= 1
    assert report["signatures"]["online_selected"] != report["signatures"]["replay_selected"]
    assert report["selected_contract"]["ok"] is True


def test_run_replay_report_ignore_field_can_suppress_ts_diff() -> None:
    now_ms = int(time.time() * 1000)
    event = _sample_event(now_ms)
    tool = build_default_replay_tool()
    replay = tool.replay([event])
    fake = _FakeRedisRange()
    fake.add("ec:raw", f"{now_ms}-1", asdict(event))
    online = dict(replay.selected[0])
    online["ts_ms"] = now_ms + 999
    fake.add("ec:selected", f"{now_ms}-2", online)

    report_without_ignore = run_replay_report(fake, start_ms=now_ms - 1, end_ms=now_ms + 2000)
    assert report_without_ignore["ok"] is False

    report_with_ignore = run_replay_report(
        fake,
        start_ms=now_ms - 1,
        end_ms=now_ms + 2000,
        ignore_fields=["ts_ms"],
    )
    assert report_with_ignore["ok"] is True
    assert report_with_ignore["diffs"] == []


def test_run_replay_report_selected_contract_invalid_when_extra_field_present() -> None:
    now_ms = int(time.time() * 1000)
    event = _sample_event(now_ms)
    tool = build_default_replay_tool()
    replay = tool.replay([event])
    fake = _FakeRedisRange()
    fake.add("ec:raw", f"{now_ms}-1", asdict(event))
    online = dict(replay.selected[0])
    online["extra_debug"] = {"a": 1}
    fake.add("ec:selected", f"{now_ms}-2", online)
    report = run_replay_report(fake, start_ms=now_ms - 1, end_ms=now_ms + 2000)
    assert report["selected_contract"]["ok"] is False
    assert report["ok"] is False
    assert any(e.get("error") == "unexpected_fields" for e in report["selected_contract"]["errors"])


def test_run_replay_report_marks_missing_streams() -> None:
    now_ms = int(time.time() * 1000)
    event = _sample_event(now_ms)
    fake = _FakeRedisRange()
    fake.add("ec:raw", f"{now_ms}-1", asdict(event))

    report = run_replay_report(fake, start_ms=now_ms - 1, end_ms=now_ms + 1)
    assert report["stream_presence"]["raw"] == "present"
    assert report["stream_presence"]["selected"] == "missing"
    assert report["missing_streams"] == ["selected"]
