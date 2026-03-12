# ports 模块说明

## 路径

- canonical：`services/feature_service/src/ports/*.py`
- 兼容壳：`feature_service/ports/*.py`


## 功能作用

`ports/` 定义 feature_service 对底层数据能力的抽象接口（Protocol）：

- `OrderbookProvider`
- `OpenInterestProvider`
- `HorizonsProvider`
- `BehaviorProvider`
- `IndicatorsProvider`

每个接口统一为异步方法，输入 `(exchange, symbol)`，输出 `Dict[str, Any]`。

## 输入输出

- 输入：无（定义层）
- 输出：依赖倒置契约（供 providers 实现、service 调用）

## 关键价值

- 让 service 不依赖具体实现（迁移版、静态版、Noop、未来在线版）
- 降低替换 provider 时对业务代码的侵入

## 迭代方向建议

1. 将 `Dict[str, Any]` 逐步替换为 TypedDict/Pydantic 模型，提前暴露字段不兼容问题。
2. 为每个 port 明确最小必需字段和可选字段文档，避免“接口签名稳定但语义漂移”。
3. 补充契约测试模板，要求新 provider 实现必须通过统一测试集。
