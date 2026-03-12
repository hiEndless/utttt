#!/usr/bin/env bash
set -euo pipefail

OUT_PATH="verification/reports/agent_readyz.latest.json"
AGENT_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
TIMEOUT_S="${AGENT_READYZ_TIMEOUT_S:-2.0}"

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/run_agent_readyz_report.sh [output_path]
  bash tools/local/run_agent_readyz_report.sh --output <path> [--base-url <url>] [--timeout-s <seconds>]

Options:
  --output <path>     readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --base-url <url>    agent 服务地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --timeout-s <sec>   HTTP 请求超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --help, -h          显示帮助
USAGE
      exit 0
      ;;
    --output)
      OUT_PATH="${2:-$OUT_PATH}"
      shift 2
      ;;
    --base-url)
      AGENT_BASE_URL="${2:-$AGENT_BASE_URL}"
      shift 2
      ;;
    --timeout-s)
      TIMEOUT_S="${2:-$TIMEOUT_S}"
      shift 2
      ;;
    *)
      if [[ "$OUT_PATH" == "verification/reports/agent_readyz.latest.json" ]]; then
        OUT_PATH="$1"
        shift
      else
        echo "[失败] 不支持的参数: $1"
        exit 1
      fi
      ;;
  esac
done

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

READYZ_URL="${AGENT_BASE_URL%/}/internal/agent/readyz"

"$PY_BIN" - "$READYZ_URL" "$OUT_PATH" "$TIMEOUT_S" <<'PY'
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict


def _normalize_payload(payload: Dict[str, Any], *, url: str, collected_at_ms: int) -> Dict[str, Any]:
    warnings = payload.get("warnings")
    errors = payload.get("errors")
    checks = payload.get("checks")
    out = {
        "schema_version": "agent-readyz-report-v1",
        "source_url": url,
        "collected_at_ms": int(collected_at_ms),
        "ok": bool(payload.get("ok")),
        "status_level": str(payload.get("status_level") or "").strip().lower(),
        "runtime_profile": str(payload.get("runtime_profile") or "").strip().lower(),
        "warnings": [str(x or "").strip() for x in warnings if str(x or "").strip()] if isinstance(warnings, list) else [],
        "errors": [str(x or "").strip() for x in errors if str(x or "").strip()] if isinstance(errors, list) else [],
        "checks": checks if isinstance(checks, dict) else {},
        "raw_readyz": payload,
    }
    if out["status_level"] not in {"green", "yellow", "red"}:
        out["status_level"] = "green" if out["ok"] else "red"
    return out


def _failure_payload(*, url: str, collected_at_ms: int, error: str) -> Dict[str, Any]:
    return {
        "schema_version": "agent-readyz-report-v1",
        "source_url": url,
        "collected_at_ms": int(collected_at_ms),
        "ok": False,
        "status_level": "red",
        "runtime_profile": "",
        "warnings": [],
        "errors": ["readyz_unreachable"],
        "checks": {},
        "raw_readyz": {"error": error},
    }


def main() -> int:
    url = str(sys.argv[1])
    output = Path(str(sys.argv[2]))
    timeout_s = float(sys.argv[3])
    now_ms = int(time.time() * 1000)
    payload: Dict[str, Any]
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # nosec B310
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("readyz response is not object")
            payload = _normalize_payload(data, url=url, collected_at_ms=now_ms)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        payload = _failure_payload(url=url, collected_at_ms=now_ms, error=str(exc))

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
