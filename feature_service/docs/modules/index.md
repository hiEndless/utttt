# feature_service 模块文档索引

本文档组面向当前 `feature_service` 代码结构，按模块拆分功能说明和迭代建议。

当前 canonical 源码路径：

- `services/feature_service/src/*`

兼容说明：

- `feature_service/*` 仍保留兼容壳（迁移窗口内可继续导入），但不再作为主实现维护路径。

重构完成态总览文档：

- [feature_service 重构完成态说明](../refactor-overview.md)

## 核心入口

- [app.py](./app.md)
- [main.py](./main.md)
- [routes.py](./routes.md)
- [contracts.py](./contracts.md)
- [service.py](./service.md)

## 支撑模块

- [normalizers/](./normalizers.md)
- [ports/](./ports.md)
- [未来数据源骨架](./future-sources.md)

## provider 体系

- [providers/bundle.py](./providers-bundle.md)
- [providers/fallback_structure_providers.py](./providers-fallback.md)
- [providers/migrated_structure_providers.py](./providers-migrated.md)
- [providers/indicators_provider.py](./providers-indicators.md)
- [providers/degradation_state.py](./providers-degradation-state.md)
- [providers/static_structure_providers.py + providers/noop.py](./providers-static-noop.md)
- [providers/market_structure_migrated/](./providers-market-structure-migrated.md)

## 推荐阅读顺序

1. `app.py` -> `routes.py` -> `service.py`（请求主链路）
2. `ports/` -> `providers/*`（依赖注入与降级链路）
3. `normalizers/`（输出稳定性）
4. `market_structure_migrated/`（核心结构计算）
