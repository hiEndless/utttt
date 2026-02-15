# agent_server 内部接口（internal_api）

## 目的

仅供“内部后端 API 服务层”调用，用于：
- 手动刷新多周期 K 线背景（写入 Redis：`background:{exchange}:{symbol}:{interval}`）
- 手动刷新市场结构背景（写入 Redis：`background:{exchange}:{symbol}:market_state`）
- 临时手动触发工作流（`signal_validation` / `trade_event`）

## 启动

```bash
export INTERNAL_AGENT_TOKEN=dev
export INTERNAL_AGENT_API_HOST=127.0.0.1
export INTERNAL_AGENT_API_PORT=9941

python -m agent_server.internal_api_main
```

## 鉴权

请求头：
- `X-Internal-Token: <INTERNAL_AGENT_TOKEN>`

说明：
- 如果没有配置 `INTERNAL_AGENT_TOKEN`（空字符串），接口将放行（便于本地开发）。

## 接口

### 健康检查

```bash
curl -sS -H 'X-Internal-Token: dev' \
  http://127.0.0.1:9941/internal/healthz
```

### 刷新市场结构背景（market_state）

```bash
curl -sS -H 'X-Internal-Token: dev' -H 'Content-Type: application/json' \
  -d '{"exchange":"binance","symbol":"ETHUSDT"}' \
  http://127.0.0.1:9941/internal/refresh/market_state
```

### 刷新 K 线背景（多周期）

注意：该接口会调用 `API_BASE_URL` 指向的后端指标读取接口 `/api/kline/indicators/read`。

```bash
export API_BASE_URL=http://127.0.0.1:9931/api

curl -sS -H 'X-Internal-Token: dev' -H 'Content-Type: application/json' \
  -d '{"exchange":"binance","symbol":"ETHUSDT","intervals":["5m","15m"],"max_concurrency":2}' \
  http://127.0.0.1:9941/internal/refresh/kline
```

### 构建并返回裁剪后的 agent context

```bash
curl -sS -H 'X-Internal-Token: dev' -H 'Content-Type: application/json' \
  -d '{"agent":"decision","exchange":"binance","symbol":"ETHUSDT","horizon":"mid_term"}' \
  http://127.0.0.1:9941/internal/context/build
```

### 手动触发工作流

```bash
curl -sS -H 'X-Internal-Token: dev' -H 'Content-Type: application/json' \
  -d '{"payload": {"route":"mixed","exchange":"binance","symbol":"ETHUSDT","event_id":"demo","event_type":"market.structure","timestamp":"0","trade_details":{}}}' \
  http://127.0.0.1:9941/internal/workflow/signal_validation
```

