#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH=""
OUTPUT_PATH="verification/reports/execution_prompt_version.latest.json"
BASE_URL="${EXECUTION_BASE_URL:-http://127.0.0.1:9962}"
TIMEOUT_S="5"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_execution_prompt_version_report.sh [options]

Options:
  --input <path>      输入 JSON 路径（内容为 /internal/execution/debug/confidence-metrics 响应）
  --output <path>     输出报告路径（默认 verification/reports/execution_prompt_version.latest.json）
  --base-url <url>    execution_service 基础地址（默认 http://127.0.0.1:9962）
  --timeout-s <sec>   HTTP 超时秒数（默认 5）
  --help, -h          显示帮助

Description:
  生成 execution prompt 版本观测报告。
  若指定 --input 则读取本地 JSON；否则请求:
  {base_url}/internal/execution/debug/confidence-metrics
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --input)
      INPUT_PATH="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-$OUTPUT_PATH}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-$BASE_URL}"
      shift 2
      ;;
    --timeout-s)
      TIMEOUT_S="${2:-$TIMEOUT_S}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      print_help
      exit 1
      ;;
  esac
done

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

"$PY_BIN" - "$INPUT_PATH" "$OUTPUT_PATH" "$BASE_URL" "$TIMEOUT_S" <<'PY'
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict
import sys

if len(sys.argv) != 5:
    raise SystemExit("usage: <input_path> <output_path> <base_url> <timeout_s>")

input_path = str(sys.argv[1] or "").strip()
output_path = Path(sys.argv[2])
base_url = str(sys.argv[3] or "").rstrip("/")
timeout_s = float(sys.argv[4] or 5)


def _load_source() -> tuple[Dict[str, Any], str]:
    if input_path:
        p = Path(input_path)
        if not p.is_file():
            raise SystemExit(f"input file not found: {p}")
        return dict(json.loads(p.read_text(encoding="utf-8"))), f"file:{p}"
    url = f"{base_url}/internal/execution/debug/confidence-metrics"
    with urllib.request.urlopen(url, timeout=timeout_s) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    return dict(data or {}), f"http:{url}"


payload, source = _load_source()
confidence = dict(payload.get("confidence_migration_metrics") or {})
prompt = dict(payload.get("prompt_config_version_metrics") or {})

prompt_counts: Dict[str, int] = {}
for k, v in prompt.items():
    key = str(k or "").strip()
    if not key:
        continue
    try:
        prompt_counts[key] = max(0, int(v))
    except Exception:
        continue

tracked_requests_total = int(sum(prompt_counts.values()))
decide_requests_total = int(confidence.get("decide_requests_total") or 0)
coverage_ratio = round(float(tracked_requests_total) / float(decide_requests_total), 6) if decide_requests_total > 0 else 0.0

versions = sorted(prompt_counts.items(), key=lambda x: (-int(x[1]), x[0]))
version_items = []
for version, count in versions:
    ratio = round(float(count) / float(tracked_requests_total), 6) if tracked_requests_total > 0 else 0.0
    version_items.append({"prompt_config_version": version, "count": int(count), "ratio": ratio})

report = {
    "schema_version": "execution-prompt-version-report-v1",
    "generated_at_ms": int(time.time() * 1000),
    "source": source,
    "summary": {
        "decide_requests_total": decide_requests_total,
        "tracked_prompt_requests_total": tracked_requests_total,
        "prompt_version_count": len(version_items),
        "tracking_coverage_ratio": coverage_ratio,
    },
    "versions": version_items,
}

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] wrote {output_path}")
print(
    f"[info] decide_requests_total={report['summary']['decide_requests_total']} "
    f"tracked_prompt_requests_total={report['summary']['tracked_prompt_requests_total']} "
    f"prompt_version_count={report['summary']['prompt_version_count']} "
    f"tracking_coverage_ratio={report['summary']['tracking_coverage_ratio']}"
)
PY
