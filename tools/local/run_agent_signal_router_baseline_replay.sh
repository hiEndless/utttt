#!/usr/bin/env bash
set -euo pipefail

SAMPLES_PATH="services/agent_server_new/config/signal_router_baseline_samples.json"
FORMAT="table"
OUTPUT_PATH=""
STRICT="1"

print_help() {
  cat <<'USAGE'
Usage:
  bash tools/local/run_agent_signal_router_baseline_replay.sh [options]

Options:
  --samples <path>  基线路由样本 JSON（默认 services/agent_server_new/config/signal_router_baseline_samples.json）
  --format <type>   输出格式（table|json，默认 table）
  --output <path>   输出文件路径（仅 format=json 时生效）
  --strict <0|1>    是否在任一样本不匹配时返回失败（默认 1）
  --help, -h        显示帮助

Description:
  按样本回放 signal_router，验证 payload -> decision_agent_key 是否符合预期。
  若样本包含 expected_normalized_event_type/expected_match_mode，也会同步校验归一化结果。
USAGE
}

while (($# > 0)); do
  case "$1" in
    --help|-h)
      print_help
      exit 0
      ;;
    --samples)
      SAMPLES_PATH="${2:-$SAMPLES_PATH}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-$FORMAT}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-$OUTPUT_PATH}"
      shift 2
      ;;
    --strict)
      STRICT="${2:-$STRICT}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1" >&2
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

"$PY_BIN" - "$SAMPLES_PATH" "$FORMAT" "$OUTPUT_PATH" "$STRICT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from services.agent_server_new.domain.signal_router import normalize_signal_event_type, route_signal_agent_key

if len(sys.argv) != 5:
    raise SystemExit("usage: <samples_path> <format> <output_path> <strict>")

samples_path = Path(sys.argv[1])
output_format = str(sys.argv[2] or "table").strip().lower()
output_path = str(sys.argv[3] or "").strip()
strict_raw = str(sys.argv[4] or "1").strip()
if output_format not in {"table", "json"}:
    raise SystemExit("[failed] --format must be one of: table|json")
if output_path and output_format != "json":
    raise SystemExit("[failed] --output requires --format json")
if strict_raw not in {"0", "1"}:
    raise SystemExit("[failed] --strict must be 0 or 1")
strict_mode = strict_raw == "1"

if not samples_path.is_file():
    raise SystemExit(f"[failed] samples file not found: {samples_path}")

try:
    samples = json.loads(samples_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"[failed] invalid samples json: {exc}")
if not isinstance(samples, list):
    raise SystemExit("[failed] samples root must be a json array")

rows: list[dict[str, object]] = []
ok = True
for idx, item in enumerate(samples, start=1):
    sample = dict(item or {})
    case_id = str(sample.get("case_id") or f"case_{idx}").strip() or f"case_{idx}"
    payload = dict(sample.get("payload") or {})
    expected_agent_key = str(sample.get("expected_agent_key") or "").strip().lower()
    expected_normalized = str(sample.get("expected_normalized_event_type") or "").strip().lower()
    expected_match_mode = str(sample.get("expected_match_mode") or "").strip().lower()
    actual_agent_key = route_signal_agent_key(signal_event={"payload": payload})
    diag = normalize_signal_event_type(signal_event={"payload": payload})
    actual_normalized = str(diag.get("normalized_event_type") or "").strip().lower()
    actual_match_mode = str(diag.get("matched") or "").strip().lower()
    route_match = bool(expected_agent_key and actual_agent_key == expected_agent_key)
    normalized_match = True if not expected_normalized else actual_normalized == expected_normalized
    match_mode_match = True if not expected_match_mode else actual_match_mode == expected_match_mode
    passed = route_match and normalized_match and match_mode_match
    ok = ok and passed
    rows.append(
        {
            "case_id": case_id,
            "expected_agent_key": expected_agent_key,
            "actual_agent_key": actual_agent_key,
            "route_match": route_match,
            "expected_normalized_event_type": expected_normalized,
            "actual_normalized_event_type": actual_normalized,
            "normalized_match": normalized_match,
            "expected_match_mode": expected_match_mode,
            "actual_match_mode": actual_match_mode,
            "match_mode_match": match_mode_match,
            "passed": passed,
        }
    )

result = {
    "schema_version": "agent-signal-router-baseline-replay-v1",
    "samples_path": str(samples_path),
    "count": len(rows),
    "ok": bool(ok),
    "strict_mode": strict_mode,
    "rows": rows,
}

if output_format == "json":
    rendered = json.dumps(result, ensure_ascii=False)
    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print(f"[ok] wrote {out}")
    print(rendered)
else:
    print(
        "case_id\texpected_agent_key\tactual_agent_key\troute_match\t"
        "expected_normalized\tactual_normalized\tnormalized_match\t"
        "expected_match_mode\tactual_match_mode\tmatch_mode_match\tpassed"
    )
    for row in rows:
        print(
            f"{str(row.get('case_id') or '')}\t"
            f"{str(row.get('expected_agent_key') or '')}\t"
            f"{str(row.get('actual_agent_key') or '')}\t"
            f"{str(row.get('route_match') or False)}\t"
            f"{str(row.get('expected_normalized_event_type') or '')}\t"
            f"{str(row.get('actual_normalized_event_type') or '')}\t"
            f"{str(row.get('normalized_match') or False)}\t"
            f"{str(row.get('expected_match_mode') or '')}\t"
            f"{str(row.get('actual_match_mode') or '')}\t"
            f"{str(row.get('match_mode_match') or False)}\t"
            f"{str(row.get('passed') or False)}"
        )

if strict_mode and not ok:
    raise SystemExit(1)
PY
