#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 运行 runtime 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  event_center_new/text/test_main.py \
  event_center_new/text/test_runner.py

echo "[2/2] 验证 stop_on_error 运行时分支"
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

echo "[通过] event_center runtime 守卫检查完成。"
