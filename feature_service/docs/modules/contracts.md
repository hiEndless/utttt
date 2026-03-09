# contracts.py 模块说明

## 功能作用

`contracts.py` 定义 feature_service 的对外响应契约模型：

- `ResponseMeta`
- `RawStructureSnapshot` / `RawStructureResponse`
- `FeatureSnapshot` / `FeatureResponse`

并固定 `SCHEMA_VERSION = "1.0"`。

## 输入输出

- 输入：routes 层组装的字段
- 输出：Pydantic 模型（用于响应校验与 OpenAPI 生成）

## 关键价值

- 契约显式化，避免隐式字典漂移
- 通过 `schema_version` 支持下游兼容分流

## 迭代方向建议

1. 为核心子结构补充更细粒度类型（从 `Dict[str, Any]` 逐步收敛）。
2. 增加版本演进策略（`1.x` 向后兼容、`2.0` 破坏性变更规则）。
3. 把错误响应体也模型化，统一 OpenAPI 表达和客户端 SDK 生成。
