from __future__ import annotations

import contextlib
import io
import logging
import os
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import services.event_center_new.runtime.main as main_mod


class _LoopRunner:
    def __init__(self) -> None:
        self.calls = 0
        self.flags: list[bool] = []

    def run_once(self, *, stop_on_error: bool = False):  # noqa: ANN001, ANN201
        self.calls += 1
        self.flags.append(stop_on_error)
        if stop_on_error:
            raise RuntimeError("boom:stop_on_error")
        return []

    def health_snapshot(self):  # noqa: ANN201
        return type("H", (), {"heartbeat": self.calls, "last_run_ms": 1, "run_count": self.calls, "error_count": 0, "last_error": ""})()


class _MainFakeRunner:
    run_once_calls = 0

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        _ = (args, kwargs)

    def run_once(self, *, stop_on_error: bool = False):  # noqa: ANN001, ANN201
        _ = stop_on_error
        _MainFakeRunner.run_once_calls += 1
        return []

    def health_snapshot(self):  # noqa: ANN201
        return type("H", (), {"heartbeat": 0, "last_run_ms": 0, "run_count": 0, "error_count": 0, "last_error": ""})()


class _FakeStore:
    pass


def test_runtime_stop_on_error_branches() -> None:
    logging.getLogger("event_center_new").disabled = True

    runner_ok = _LoopRunner()
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        main_mod._run_loop(runner_ok, interval_ms=1, max_ticks=2, stop_on_error=False, sleep_fn=lambda _s: None)
    assert runner_ok.calls == 2
    assert runner_ok.flags == [False, False]

    runner_fail = _LoopRunner()
    raised = False
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main_mod._run_loop(runner_fail, interval_ms=1, max_ticks=2, stop_on_error=True, sleep_fn=lambda _s: None)
    except RuntimeError:
        raised = True
    assert raised is True
    assert runner_fail.flags == [True]


def test_runtime_self_check_only_skips_event_processing(monkeypatch) -> None:  # noqa: ANN001
    called = {"self_check": 0}

    def _fake_self_check(*, layer_store, health_key: str) -> None:  # noqa: ANN001
        assert isinstance(layer_store, _FakeStore)
        assert health_key == "ec:self:health"
        called["self_check"] += 1

    monkeypatch.setattr(main_mod, "_build_layer_store", lambda: _FakeStore())
    monkeypatch.setattr(main_mod, "_run_self_check", _fake_self_check)
    monkeypatch.setattr(main_mod, "_run_loop", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected loop")))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "_run_once_and_log", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected once")))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "EventPipelineRunner", _MainFakeRunner)
    monkeypatch.setenv("EVENT_CENTER_SELF_CHECK_ONLY", "true")
    monkeypatch.setenv("EVENT_CENTER_HEALTH_KEY", "ec:self:health")

    _MainFakeRunner.run_once_calls = 0
    main_mod.main()
    assert called["self_check"] == 1
    assert _MainFakeRunner.run_once_calls == 0
    os.environ.pop("EVENT_CENTER_SELF_CHECK_ONLY", None)
    os.environ.pop("EVENT_CENTER_HEALTH_KEY", None)
