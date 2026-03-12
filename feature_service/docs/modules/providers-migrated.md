# providers/migrated_structure_providers.py 模块说明

## 路径

- canonical：`services/feature_service/src/providers/migrated_structure_providers.py`
- 兼容壳：已在 Batch B 下线


## 功能作用

该模块是迁移版结构 provider 入口，将四类结构能力映射到 `market_structure_migrated` 子模块：

- `MigratedOrderbookProvider`
- `MigratedOpenInterestProvider`
- `MigratedHorizonsProvider`
- `MigratedBehaviorProvider`

每个 provider 只做一层委托：调用对应 `build_output(...)`，再统一 `dict(...)` 返回。

## 输入输出

- 输入：`exchange`、`symbol`
- 输出：对应结构的字典结果

## 关键价值

- 将历史算法代码隔离在独立子目录，主流程只依赖标准 provider 接口
- 为后续逐步替换算法实现提供稳定外壳

## 迭代方向建议

1. 为每类 provider 增加超时保护（防止单个计算链路阻塞聚合）。
2. 引入结果校验层（schema check），防止迁移算法输出异常结构直通上游。
3. 分阶段替换为“原生 feature_service 算法实现”，减少历史包袱。
