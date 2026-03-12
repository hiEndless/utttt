#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] 检查 replay CLI strict CI 参数"
help_text="$(python3 -m services.event_center_new.replay_main --help)"
if ! echo "$help_text" | rg -q -- "--strict"; then
  echo "[失败] replay CLI 缺少 --strict 参数"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--summary-only"; then
  echo "[失败] replay CLI 缺少 --summary-only 参数"
  exit 1
fi

echo "[2/2] 验证 strict+summary-only 成功/失败路径"
python3 - <<'PY'
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

PROJECT_ROOT = str(Path.cwd())
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


sys.modules["redis"] = _FakeRedisModule()

# 成功路径：strict 打开时，契约通过、无 diff、无缺失 stream，应该返回 0。
replay_main.run_replay_report = lambda *args, **kwargs: {  # type: ignore[assignment]
    "ok": True,
    "diffs": [],
    "missing_streams": [],
    "selected_contract": {"ok": True},
}
with contextlib.redirect_stdout(io.StringIO()):
    ok_code = replay_main.main(["--start-ms", "1", "--end-ms", "2", "--strict", "--summary-only"])
if ok_code != 0:
    raise SystemExit(1)

# 失败路径：strict 打开时，任一 fail 条件命中应返回非 0。
replay_main.run_replay_report = lambda *args, **kwargs: {  # type: ignore[assignment]
    "ok": True,
    "diffs": ["x"],
    "missing_streams": [],
    "selected_contract": {"ok": True},
}
with contextlib.redirect_stdout(io.StringIO()):
    fail_code = replay_main.main(["--start-ms", "1", "--end-ms", "2", "--strict", "--summary-only"])
if fail_code == 0:
    raise SystemExit(1)
PY

echo "[通过] event_center replay strict CI 守卫检查完成。"
