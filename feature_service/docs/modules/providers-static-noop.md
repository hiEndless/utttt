# providers/static_structure_providers.py + providers/noop.py 模块说明

## 路径

- canonical：`services/feature_service/src/providers/static_structure_providers.py` 与 `services/feature_service/src/providers/noop.py`
- 兼容壳：`feature_service/providers/static_structure_providers.py` 与 `feature_service/providers/noop.py`


## 功能作用

这两个模块提供兜底 provider：

- `static_structure_providers.py`
  - 返回可配置静态 payload（`deepcopy` 防止被调用方污染）
- `noop.py`
  - 返回空结构 `{}`，用于最小可运行/测试场景

## 输入输出

- 输入：可选静态 payload（仅 static provider）
- 输出：稳定字典结构

## 关键价值

- 保证在主路径不可用时服务仍可启动与返回可解释结果
- 为契约测试提供可预测的低成本依赖

## 迭代方向建议

1. 增加“最小合法结构模板”，替代完全空字典，降低下游分支复杂度。
2. 对 static provider 增加按 symbol/exchange 的模板映射能力。
3. 统一静态兜底输出中的元信息（如 `source=static_fallback`）便于定位。
