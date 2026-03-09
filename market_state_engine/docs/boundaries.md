# market_state_engine Boundaries

## 只负责什么

- 消费 feature / raw structure
- 仅处理市场结构相关输入（价格结构、订单簿、OI、波动、多周期一致性）
- 聚合状态证据
- 识别 anomaly
- 识别 regime
- 产出 MSL
- 向决策层服务化输出状态

## 明确不负责什么

- 不采集原始市场数据
- 不计算基础指标
- 不做事件 dedup / classify / prioritize
- 不直接处理新闻舆情 / 社媒 / 链上事件流
- 不做 signal evaluation / strategy planning
- 不做 execution planning / order routing

## 与 `feature_service` 的边界

`feature_service` 负责：

- 指标计算
- 派生 metrics
- raw structure 标准化

`market_state_engine` 负责：

- 基于这些输入生成市场状态
- 当上游返回 `feature_data_unavailable` 时，短路推断并输出 `status=data_unavailable`
- 忽略输入中混入的外部事件字段（如 `news/social/onchain`），并记录边界守卫标记

## 与 `agent_server_new` 的边界

`market_state_engine` 只输出状态，不输出动作。

`agent_server_new` 只消费状态，不反向生成 MSL。
