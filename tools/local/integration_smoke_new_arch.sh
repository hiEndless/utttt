#!/usr/bin/env bash
set -euo pipefail

# 新架构最小联调冒烟脚本（feature -> state）
# 用法：
#   FEATURE_BASE_URL=http://127.0.0.1:8001 \
#   STATE_BASE_URL=http://127.0.0.1:8002 \
#   EXCHANGE=binance \
#   SYMBOL=ETHUSDT \
#   bash tools/local/integration_smoke_new_arch.sh

FEATURE_BASE_URL="${FEATURE_BASE_URL:-http://127.0.0.1:8001}"
STATE_BASE_URL="${STATE_BASE_URL:-http://127.0.0.1:8002}"
EXCHANGE="${EXCHANGE:-binance}"
SYMBOL="${SYMBOL:-ETHUSDT}"

echo "[1/4] 检查 feature_service healthz"
curl -sS "${FEATURE_BASE_URL}/internal/feature-service/healthz" | jq .

echo "[2/4] 查询 feature raw-structure"
FEATURE_HTTP_CODE="$(curl -sS -o /tmp/feature_raw.json -w "%{http_code}" \
  "${FEATURE_BASE_URL}/internal/feature-service/raw-structure/${EXCHANGE}/${SYMBOL}")"
echo "feature raw-structure HTTP: ${FEATURE_HTTP_CODE}"
cat /tmp/feature_raw.json | jq .

if [[ "${FEATURE_HTTP_CODE}" == "503" ]]; then
  echo "[提示] feature 返回 503（feature_data_unavailable），继续验证 state 短路语义。"
fi

echo "[3/4] 检查 market_state_engine healthz"
curl -sS "${STATE_BASE_URL}/internal/market-state/healthz" | jq .

echo "[4/4] 查询 market state"
STATE_HTTP_CODE="$(curl -sS -o /tmp/state_snapshot.json -w "%{http_code}" \
  "${STATE_BASE_URL}/internal/market-state/${EXCHANGE}/${SYMBOL}")"
echo "market-state HTTP: ${STATE_HTTP_CODE}"
cat /tmp/state_snapshot.json | jq .

echo "[完成] 新架构最小联调冒烟执行结束。"
