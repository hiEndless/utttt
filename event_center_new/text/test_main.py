from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import event_center_new.main as main_mod


@dataclass
class _Health:
    heartbeat: int
    last_run_ms: int
    run_count: int
    error_count: int
    last_error: str


class _FakeRunner:
    def __init__(self) -> None:
        self.calls = 0
        self.flags: list[bool] = []

    def run_once(self, *, stop_on_error: bool = False):  # noqa: ANN001, ANN201
        self.calls += 1
        self.flags.append(stop_on_error)
        return []

    def health_snapshot(self) -> _Health:
        return _Health(
            heartbeat=self.calls,
            last_run_ms=1,
            run_count=self.calls,
            error_count=0,
            last_error="",
        )


class _FakeHealthStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def write_runner_health(self, payload: dict, *, key: str = "ec:runner:health") -> None:
        self.calls.append((key, dict(payload)))


class _FakePipelineRunner:
    run_once_calls = 0

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        _ = (args, kwargs)

    def run_once(self, *, stop_on_error: bool = False):  # noqa: ANN001, ANN201
        _ = stop_on_error
        _FakePipelineRunner.run_once_calls += 1
        return []

    def health_snapshot(self) -> _Health:
        return _Health(heartbeat=0, last_run_ms=0, run_count=0, error_count=0, last_error="")


def test_run_loop_respects_max_ticks() -> None:
    runner = _FakeRunner()
    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)

    main_mod._run_loop(runner, interval_ms=200, max_ticks=3, sleep_fn=_sleep)
    assert runner.calls == 3
    assert sleeps == [0.2, 0.2]
    assert runner.flags == [False, False, False]


def test_run_loop_passes_stop_on_error_flag() -> None:
    runner = _FakeRunner()
    main_mod._run_loop(runner, interval_ms=10, max_ticks=2, stop_on_error=True, sleep_fn=lambda _s: None)
    assert runner.flags == [True, True]


def test_publish_runner_health_uses_store_writer() -> None:
    store = _FakeHealthStore()
    main_mod._publish_runner_health(store, payload={"heartbeat": 1}, key="ec:test:health")
    assert len(store.calls) == 1
    key, payload = store.calls[0]
    assert key == "ec:test:health"
    assert payload["heartbeat"] == 1
    assert isinstance(payload.get("updated_ms"), int)


def test_run_self_check_writes_health_status() -> None:
    store = _FakeHealthStore()
    main_mod._run_self_check(layer_store=store, health_key="ec:self:health")
    assert len(store.calls) == 1
    key, payload = store.calls[0]
    assert key == "ec:self:health"
    assert payload["status"] == "ok"
    assert payload["self_check_only"] is True


def test_main_self_check_only_skips_run_once(monkeypatch) -> None:  # noqa: ANN001
    store = _FakeHealthStore()
    called: dict[str, int] = {"self_check": 0}

    def _fake_self_check(*, layer_store, health_key: str) -> None:  # noqa: ANN001
        assert layer_store is store
        assert health_key == "ec:self:health"
        called["self_check"] += 1

    monkeypatch.setenv("EVENT_CENTER_SELF_CHECK_ONLY", "true")
    monkeypatch.setenv("EVENT_CENTER_HEALTH_KEY", "ec:self:health")
    monkeypatch.setattr(main_mod, "_build_layer_store", lambda: store)
    monkeypatch.setattr(main_mod, "_run_self_check", _fake_self_check)
    monkeypatch.setattr(main_mod, "_run_loop", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected loop")))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "_run_once_and_log", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected run_once")))  # noqa: ARG005
    monkeypatch.setattr(main_mod, "EventPipelineRunner", _FakePipelineRunner)

    _FakePipelineRunner.run_once_calls = 0
    main_mod.main()
    assert called["self_check"] == 1
    assert _FakePipelineRunner.run_once_calls == 0


def test_read_bool_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EC_BOOL_X", "true")
    assert main_mod._read_bool_env("EC_BOOL_X", default=False) is True
    monkeypatch.setenv("EC_BOOL_X", "0")
    assert main_mod._read_bool_env("EC_BOOL_X", default=True) is False
    monkeypatch.setenv("EC_BOOL_X", "unknown")
    assert main_mod._read_bool_env("EC_BOOL_X", default=True) is True


def test_read_int_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("EC_INT_X", "123")
    assert main_mod._read_int_env("EC_INT_X", default=9) == 123
    monkeypatch.setenv("EC_INT_X", "x")
    assert main_mod._read_int_env("EC_INT_X", default=9) == 9
