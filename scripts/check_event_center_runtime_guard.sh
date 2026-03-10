#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 运行 runtime 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  event_center_new/text/test_main.py \
  event_center_new/text/test_runner.py

echo "[2/3] 验证 stop_on_error 运行时分支"
python3 - <<'PY'
from __future__ import annotations

import contextlib
import io
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = str(Path.cwd())
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import event_center_new.main as main_mod
logging.getLogger("event_center_new").disabled = True


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
        if stop_on_error:
            raise RuntimeError("boom:stop_on_error")
        return []

    def health_snapshot(self) -> _Health:
        return _Health(
            heartbeat=self.calls,
            last_run_ms=1,
            run_count=self.calls,
            error_count=0,
            last_error="",
        )


# stop_on_error=false: 不应抛错，且应跑满 max_ticks。
runner_ok = _FakeRunner()
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    main_mod._run_loop(runner_ok, interval_ms=1, max_ticks=2, stop_on_error=False, sleep_fn=lambda _s: None)
if runner_ok.calls != 2:
    raise SystemExit(1)
if runner_ok.flags != [False, False]:
    raise SystemExit(1)

# stop_on_error=true: 第一轮即抛错退出。
runner_fail = _FakeRunner()
raised = False
try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        main_mod._run_loop(runner_fail, interval_ms=1, max_ticks=2, stop_on_error=True, sleep_fn=lambda _s: None)
except RuntimeError:
    raised = True
if not raised:
    raise SystemExit(1)
if runner_fail.flags != [True]:
    raise SystemExit(1)
PY

echo "[3/3] 验证 self_check_only 不进入事件处理分支"
python3 - <<'PY'
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = str(Path.cwd())
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import event_center_new.main as main_mod


class _FakeRunner:
    run_once_calls = 0

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        _ = (args, kwargs)

    def run_once(self, *, stop_on_error: bool = False):  # noqa: ANN001, ANN201
        _ = stop_on_error
        _FakeRunner.run_once_calls += 1
        return []

    def health_snapshot(self):  # noqa: ANN201
        return type("H", (), {"heartbeat": 0, "last_run_ms": 0, "run_count": 0, "error_count": 0, "last_error": ""})()


class _FakeStore:
    pass


called = {"self_check": 0}


def _fake_self_check(*, layer_store, health_key: str) -> None:  # noqa: ANN001
    if not isinstance(layer_store, _FakeStore):
        raise SystemExit(1)
    if health_key != "ec:self:health":
        raise SystemExit(1)
    called["self_check"] += 1


main_mod._build_layer_store = lambda: _FakeStore()  # type: ignore[assignment]
main_mod._run_self_check = _fake_self_check  # type: ignore[assignment]
main_mod._run_loop = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected loop"))  # type: ignore[assignment]
main_mod._run_once_and_log = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected once"))  # type: ignore[assignment]
main_mod.EventPipelineRunner = _FakeRunner  # type: ignore[assignment]

os.environ["EVENT_CENTER_SELF_CHECK_ONLY"] = "true"
os.environ["EVENT_CENTER_HEALTH_KEY"] = "ec:self:health"
_FakeRunner.run_once_calls = 0
main_mod.main()
if called["self_check"] != 1:
    raise SystemExit(1)
if _FakeRunner.run_once_calls != 0:
    raise SystemExit(1)
PY

echo "[通过] event_center runtime 守卫检查完成。"
