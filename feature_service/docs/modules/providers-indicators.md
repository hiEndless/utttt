# providers/indicators_provider.py 模块说明

## 功能作用

`RedisIndicatorsProvider` 负责读取指标数据：

- 通过 `read_multi_period(exchange, symbol, periods)` 读取多周期指标
- 默认周期为 `1m/5m/15m/1h/4h/1d`

## 输入输出

- 输入：`exchange`、`symbol`、可选 `periods`
- 输出：按周期组织的指标字典

## 关键价值

- 将指标来源固定在数据服务产出，避免 feature 层重复计算基础指标
- 支持周期配置，适配不同下游策略粒度

## 迭代方向建议

1. 增加指标可用性检查（空 payload、字段缺失）并打点。
2. 引入本地缓存或短 TTL 缓存，降低高并发重复读取压力。
3. 支持按请求指定指标白名单，减少无效数据传输。
