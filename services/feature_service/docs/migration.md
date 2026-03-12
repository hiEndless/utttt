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

## 迁移增量记录

### 2026-03-13

- `FeatureResponse` 新增可选输出块 `data.alternative_sources`（`news/social/onchain`）。
- 输出语义：统一最小包结构 `source_type/available/provider_state/as_of_ms/features`，用于未来多源接入前的字段稳定占位。
- 兼容性：向后兼容（新增可选字段，不影响既有 `indicators/derived_metrics/structure_snapshot` 读取路径）。
