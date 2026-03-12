from __future__ import annotations

from pathlib import Path
import json
import sys
import types

PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import services.event_center_new.runtime.replay_main as replay_main


class _FakeRedisClient:
    pass


class _FakeRedisModule:
    class Redis:
        @staticmethod
        def from_url(url: str, decode_responses: bool = True):  # noqa: ANN001, ANN204
            _ = (url, decode_responses)
            return _FakeRedisClient()


def test_replay_main_fail_on_contract(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "ok": True,
            "diffs": [],
            "selected_contract": {"ok": False},
        },
    )
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--fail-on-contract",
        ]
    )
    assert code == 1


def test_replay_main_fail_on_diff(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "ok": True,
            "diffs": ["x"],
            "selected_contract": {"ok": True},
        },
    )
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--fail-on-diff",
        ]
    )
    assert code == 1


def test_replay_main_writes_output(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "ok": True,
            "diffs": [],
            "selected_contract": {"ok": True},
        },
    )
    out = tmp_path / "report.json"
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--output",
            str(out),
            "--compact",
        ]
    )
    assert code == 0
    assert out.is_file()
    assert out.read_text(encoding="utf-8").strip()


def test_replay_main_fail_on_missing_stream(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "ok": True,
            "diffs": [],
            "selected_contract": {"ok": True},
            "missing_streams": ["selected"],
        },
    )
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--fail-on-missing-stream",
        ]
    )
    assert code == 1


def test_replay_main_strict_implies_all_fail_flags(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "ok": True,
            "diffs": [],
            "selected_contract": {"ok": True},
            "missing_streams": ["selected"],
        },
    )
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--strict",
        ]
    )
    assert code == 1


def test_replay_main_summary_only_hides_large_fields(monkeypatch, capsys) -> None:  # noqa: ANN001
    monkeypatch.setitem(sys.modules, "redis", _FakeRedisModule())
    monkeypatch.setattr(
        replay_main,
        "run_replay_report",
        lambda *args, **kwargs: {  # noqa: ARG005
            "start_ms": 1,
            "end_ms": 2,
            "streams": {"raw": "ec:raw", "selected": "ec:selected"},
            "stream_presence": {"raw": "present", "selected": "present"},
            "missing_streams": [],
            "counts": {"raw_events": 1},
            "ok": True,
            "ignore_fields": [],
            "signatures": {"online_selected": "a", "replay_selected": "a"},
            "selected_contract": {"ok": True},
            "diffs": [],
            "replay_selected": [{"x": 1}],
            "online_selected": [{"x": 1}],
        },
    )
    code = replay_main.main(
        [
            "--start-ms",
            "1",
            "--end-ms",
            "2",
            "--summary-only",
            "--compact",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert "replay_selected" not in payload
    assert "online_selected" not in payload
    assert payload["ok"] is True
