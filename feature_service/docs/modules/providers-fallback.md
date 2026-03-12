# providers/fallback_structure_providers.py 模块说明

## 路径

- canonical：`services/feature_service/src/providers/fallback_structure_providers.py`
- 兼容壳：已在 Batch B 下线


## 功能作用

该模块提供通用 fallback 包装器：

- `FallbackOrderbookProvider`
- `FallbackOpenInterestProvider`
- `FallbackHorizonsProvider`
- `FallbackBehaviorProvider`
- `FallbackIndicatorsProvider`
- `UnavailableIndicatorsProvider`

行为模式一致：优先调用 `primary`，异常时记录降级原因并切换到 `fallback`。

## 输入输出

- 输入：`primary` 与 `fallback` provider
- 输出：统一 provider 接口实现（含降级语义）

## 关键价值

- 防止单点 provider 异常导致整个服务不可用
- 将降级事件标准化沉淀到 `degraded_reasons`

## 迭代方向建议

1. 细化异常分类（网络错误、数据错误、超时错误）并输出更可操作的降级原因。
2. 引入熔断/半开恢复机制，避免高频失败反复打主路径。
3. 增加降级率指标（按 provider、exchange、symbol）用于容量和质量治理。
