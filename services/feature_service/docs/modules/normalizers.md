# normalizers 模块说明

## 路径

- canonical：`services/feature_service/src/normalizers/*.py`
- 兼容壳：已在 Batch A 下线


## 功能作用

`normalizers/response_normalizer.py` 负责响应归一化，主要能力：

- 统一 `exchange`、`symbol` 格式
- 去重并清洗 `degraded_reasons`
- 统一 `candidate_horizons` 的合法集合和顺序
- 保证 `raw_market_structure` 与 `features` 的关键字段稳定存在

## 输入输出

- 输入：service 层组装的原始字典
- 输出：字段稳定、类型稳定的标准化字典

## 关键价值

- 降低上游抖动和字段缺失对下游的影响
- 将“契约稳定性”从业务逻辑中抽离，集中治理

## 迭代方向建议

1. 增加 normalizer 版本与变更日志，支持可追踪的 schema 演进。
2. 引入更严格的值域检查（例如状态枚举白名单）并提供纠偏统计。
3. 将“默认值注入”与“脏数据修复”拆分成两个阶段，便于观测数据质量。
