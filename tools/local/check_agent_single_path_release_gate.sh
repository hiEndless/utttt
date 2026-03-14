#!/usr/bin/env bash
set -euo pipefail

AGENT_BASE_URL="${AGENT_BASE_URL:-http://127.0.0.1:9971}"
EXECUTION_BASE_URL="${AGENT_EXECUTION_BASE_URL:-http://127.0.0.1:9962}"
TIMEOUT_S="${AGENT_RELEASE_GATE_TIMEOUT_S:-2.0}"
EXCHANGE="${AGENT_RELEASE_GATE_EXCHANGE:-binance}"
SYMBOL="${AGENT_RELEASE_GATE_SYMBOL:-ETHUSDT}"
SIGNAL_DIRECTION="${AGENT_RELEASE_GATE_SIGNAL_DIRECTION:-long}"
PAYLOAD_JSON="${AGENT_RELEASE_GATE_PAYLOAD_JSON:-{\"event_type\":\"indicator_signal\"}}"

if [[ -x "./venv/bin/python" ]]; then
  PY_BIN="./venv/bin/python"
else
  PY_BIN="python3"
fi

echo "[1/3] 检查 agent readyz"
READYZ_URL="${AGENT_BASE_URL%/}/internal/agent/readyz"
READYZ_BODY="$(curl -fsS --max-time "$TIMEOUT_S" "$READYZ_URL")"
"$PY_BIN" - "$READYZ_BODY" <<'PY'
import json
import sys

body = json.loads(sys.argv[1])
if not bool(body.get("ok")):
    raise SystemExit("agent readyz not ok")
print("agent_readyz_ok")
PY

echo "[2/3] 检查 execution healthz"
EXEC_HEALTHZ_URL="${EXECUTION_BASE_URL%/}/internal/execution/healthz"
EXEC_BODY="$(curl -fsS --max-time "$TIMEOUT_S" "$EXEC_HEALTHZ_URL")"
"$PY_BIN" - "$EXEC_BODY" <<'PY'
import json
import sys

body = json.loads(sys.argv[1])
ok = body.get("ok")
if ok is False:
    raise SystemExit("execution healthz not ok")
print("execution_healthz_ok")
PY

echo "[3/3] 运行 production runner 闭环（强制 use-execution-result）"
RUN_OUT="$(
  AGENT_RUNTIME_PROFILE=prod "$PY_BIN" -m services.agent_server_new.main \
    --exchange "$EXCHANGE" \
    --symbol "$SYMBOL" \
    --signal-direction "$SIGNAL_DIRECTION" \
    --payload-json "$PAYLOAD_JSON" \
    --use-execution-result \
    --print-json
)"
"$PY_BIN" - "$RUN_OUT" <<'PY'
import json
import sys

body = json.loads(sys.argv[1])
if str(body.get("source") or "") != "execution":
    raise SystemExit("runner output source is not execution")
print("runner_execution_source_ok")
PY

echo "[通过] 单一路径发布 gate 通过：signal -> decision agent -> execution"
