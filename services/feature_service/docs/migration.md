# feature_service Migration

## 迁移来源

建议分三批迁移能力：

### 第一批

- `data_server/binance/rest_binance/app/signals/*`

目标：

- 把基础指标计算集中到 `feature_service`

### 第二批

- `agent_server/agent_context/market_structure/orderbook/*`
- `agent_server/agent_context/market_structure/open_interest/*`

目标：

- 把 orderbook / oi 的派生结构统一沉淀为 feature

### 第三批

- `agent_server/agent_context/market_structure/horizons/*`
- 当前 `compat.market_structure` 中的聚合逻辑

目标：

- 让 `raw_market_structure` 的唯一生产者变成 `feature_service`

## 当前阶段目标

短期先实现：

1. 稳定目录
2. 稳定接口
3. 稳定 contract

再开始真实迁移逻辑。
