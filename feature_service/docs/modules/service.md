# service.py 模块说明

## 路径

- canonical：`services/feature_service/src/service.py`
- 兼容壳：已在 Batch A 下线


## 功能作用

`service.py` 是 feature_service 的业务核心层，职责包括：

- 并发拉取底层结构：
  - `orderbook`
  - `open_interest`
  - `horizons`
  - `behavioral`
  - `indicators`（仅 features 接口）
- 构建标准 `raw_market_structure`
- 派生 `derived_metrics` 与 `structure_snapshot`
- 执行输出标准化（normalizer）
- 维护请求级降级原因采集
- 在“关键结构全空”时抛出 `FeatureDataUnavailableError`

## 输入输出

- 输入：`ports` 抽象 provider 的异步结果
- 输出：
  - `get_raw_structure(...)` -> 结构快照 + 降级信息
  - `get_features(...)` -> 特征快照 + 降级信息

## 关键价值

- 统一 feature 组装和派生逻辑，避免各下游重复拼装
- 将 provider 波动通过降级语义显式暴露给下游
- 将“软降级”和“硬失败”策略分层处理

## 当前设计关注点

- 构建逻辑较大，包含领域规则与协议层语义混合（可读性和可测试性会随功能增长下降）。
- `_build_*` / `_derive_*` 函数已具备拆分条件，适合模块化。

## 迭代方向建议

1. 将 `pre_decision_structure` 构建和 `derived_metrics` 计算拆成独立子模块（例如 `assemblers/`、`derivers/`）。
2. 把阈值（如 `delta_oi_pct >= 0.03`）配置化，便于灰度与策略回测。
3. 补齐针对边界输入的单测矩阵（空结构、异常值、部分字段缺失、跨 provider 降级组合）。
4. 引入结构化埋点，输出每次请求的 provider 成功率和降级分布。
