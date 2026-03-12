# providers/bundle.py 模块说明

## 路径

- canonical：`services/feature_service/src/providers/bundle.py`
- 兼容壳：已在 Batch B 下线


## 功能作用

`bundle.py` 负责 provider 的组合与装配策略，核心包含：

- `ProviderBundle`：集中承载五类 provider
- `build_noop_provider_bundle()`：纯占位 bundle
- `build_independent_provider_bundle()`：默认独立运行 bundle（迁移版主路径 + fallback + 指标降级）

## 输入输出

- 输入：可选 `periods`（指标周期）
- 输出：可注入 `FeatureService` 的 `ProviderBundle`

## 关键价值

- 将“运行模式”从业务层抽离到装配层
- 把降级策略显式固定在构建阶段，减少调用链分散判断

## 迭代方向建议

1. 增加配置驱动装配（通过配置切换 provider 实现，而非硬编码类组合）。
2. 给 bundle 增加 `describe()` 能力，启动时打印当前 provider 拓扑。
3. 引入按 symbol/exchange 维度的 provider 路由能力（例如分交易所策略）。
