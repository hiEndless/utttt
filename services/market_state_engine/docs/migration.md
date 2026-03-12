# market_state_engine Migration

## 当前迁移状态

已经完成：

- 从 `agent_server_new` 中拆出独立目录
- 建立独立 `contracts.py`
- 建立独立 `engine.py`
- 建立独立 HTTP 服务骨架
- 已支持上游不可用短路（`status=data_unavailable`）
- 已完成插件化状态推断链路（`state_inference`）
  - 默认链路：`regime -> positioning -> volatility -> liquidity -> risk -> structure`
  - `risk_only` 最小链路：`regime -> risk`
  - `state_fusion` 统一融合中间状态
  - `msl_generator` 统一生成 `MSL`
  - 支持插件启停配置（`enabled_plugins/disabled_plugins`）
  - 支持插件 profile 预设（`default/fast_mode/risk_only`）
  - 配置优先级已冻结：`enabled_plugins` > `plugin_profile` > `default`，最后应用 `disabled_plugins`
  - profile 已下沉到 `config/state_inference_profiles.json`，支持环境变量覆盖文件路径（`MSE_STATE_PLUGIN_PROFILES_FILE`）
  - 支持推断多版本并存（同一 schema）
    - `MSE_MSL_INFERENCE_VERSION=msl_generator_v1|msl_generator_v2`
    - 输出通过 `msl_meta` 暴露 `schema_version/inference_version/inference_profile`
  - 支持多周期状态并存（`msl_bundle`）
    - `short_term/mid_term/long_term`
    - `cross_horizon` 暴露周期一致性与冲突摘要
    - 冲突字段：`trend/phase/volatility_regime/liquidity_risk`
    - 冲突优先级：`trend > phase > volatility_regime > liquidity_risk`
    - 提供执行建议：`suggested_policy/policy_reason`

## 当前输入

当前主要输入仍是：

- `raw_market_structure`

这意味着状态层已独立，但输入粒度仍偏粗。

另外，输入不可用场景已定义统一策略：

- 上游 `feature_service` 返回 `503 feature_data_unavailable` 时
- 本服务返回 `200` + `status=data_unavailable`，避免下游误判
- 上游若提供 `alternative_sources`（news/social/onchain），状态层会标准化后透传到 `state_features.evidence`，当前阶段不纳入主推断链路。
- 当 `selected_event.context_snapshot.alternative_sources_summary` 可用时，状态层会与 feature 侧来源做融合，产出 `state_features.evidence.alternative_sources_fusion`（feature 优先，event_center 补充，冲突显式记录）。

## 下一阶段

建议按以下顺序推进：

1. 稳定 `raw_market_structure`
2. 稳定 `MSL` schema
3. 引入 `feature_snapshot`
4. 引入 `selected_event / active_events`
5. 增加 state cache / replay

## 迁移目标

最终目标是让 `market_state_engine` 成为：

> 唯一的市场状态生产者，而不是 `agent_server_new` 的内部模块。
