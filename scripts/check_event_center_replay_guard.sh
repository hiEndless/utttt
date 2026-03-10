#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] 检查 event_center replay 入口文件"
if ! test -f event_center_new/replay_main.py; then
  echo "[失败] 缺少 event_center_new/replay_main.py"
  exit 1
fi
if ! test -f event_center_new/ec/pipeline/replay.py; then
  echo "[失败] 缺少 event_center_new/ec/pipeline/replay.py"
  exit 1
fi
if ! test -f event_center_new/ec/pipeline/replay_cli.py; then
  echo "[失败] 缺少 event_center_new/ec/pipeline/replay_cli.py"
  exit 1
fi

echo "[2/3] 运行 event_center replay 相关测试"
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"
./venv/bin/pytest -q \
  event_center_new/text/test_runner.py \
  event_center_new/text/test_redis_layer_store.py \
  event_center_new/text/test_replay.py \
  event_center_new/text/test_replay_cli.py \
  event_center_new/text/test_replay_main.py

echo "[3/3] 校验 replay CLI 参数"
python3 -m event_center_new.replay_main --help >/dev/null
if ! python3 -m event_center_new.replay_main --help | rg -q -- "--fail-on-missing-stream"; then
  echo "[失败] replay CLI 缺少 --fail-on-missing-stream 参数"
  exit 1
fi

echo "[附加检查] 验证缺失 stream 时 fail-on-missing-stream 返回非 0"
python3 - <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path.cwd())
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


sys.modules["redis"] = _FakeRedisModule()
replay_main.run_replay_report = lambda *args, **kwargs: {  # type: ignore[assignment]
    "ok": True,
    "diffs": [],
    "selected_contract": {"ok": True},
    "missing_streams": ["selected"],
}
code = replay_main.main(["--start-ms", "1", "--end-ms", "2", "--fail-on-missing-stream"])
if code == 0:
    raise SystemExit(1)
PY

echo "[通过] event_center replay 守卫检查完成。"
