# providers/degradation_state.py 模块说明

## 路径

- canonical：`services/feature_service/src/providers/degradation_state.py`
- 兼容壳：`feature_service/providers/degradation_state.py`


## 功能作用

该模块维护“单次请求”的降级原因集合，使用 `ContextVar` 持有状态：

- `reset_degradation_state()`
- `mark_degraded(reason)`
- `snapshot_degradation_reasons()`

## 输入输出

- 输入：降级原因字符串
- 输出：去重后的降级原因列表快照

## 关键价值

- 在异步并发场景下将降级原因和请求上下文绑定
- 为 routes 的 `meta.degraded_reasons` 提供统一来源

## 迭代方向建议

1. 引入不可变结构与 token 管理，减少可变 list 的上下文共享副作用风险。
2. 支持降级原因分级（warning/error）与来源（provider 名）。
3. 增加“本次请求是否发生降级”的快速标记位，减少重复计算。
