from __future__ import annotations

from pathlib import Path
import sys
import types

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import event_center_new.replay_main as replay_main


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
