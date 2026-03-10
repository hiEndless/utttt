# market_state_engine

项目级新架构总览：`/docs/ARCHITECTURE_NEW.md`

`market_state_engine` 是目标架构中的 **State Layer**，位于 `feature_service` 之后、`agent_server_new` 之前。

目标收敛架构：

```text
data_server
  -> feature_service
    -> event_center_new
    -> market_state_engine
      -> agent_server_new
        -> execution_service
```

## 定位

`market_state_engine` 的职责不是采集数据，也不是做交易决策，而是把结构化特征和已筛选事件归纳成稳定市场状态。

一句话定义：

> `market_state_engine` 负责把 feature data 变成 state data。

边界补充（冻结）：

- `market_state_engine` 只做“市场结构状态”分析与 MSL 产出。
- 不直接接收新闻舆情、链上、社媒等外部事件流。
- 外部事件由 `event_center_new` 直接提供给 `agent_server_new` 作为决策上下文。

## 核心职责

`market_state_engine` 只负责以下能力：

- consume feature snapshots
- consume raw market structure
- anomaly synthesis
- regime detection
- structure summary
- plugin-based state inference
- state fusion
- MSL generation
- key_features extraction
- state serving

## 不负责的事情

`market_state_engine` 不负责：

- 原始市场数据采集
  - 这是 `data_server`
- feature 计算与标准化
  - 这是 `feature_service`
- 事件去重、分类、优先级
  - 这是 `event_center_new`
- signal evaluation / rule planning / risk gating
  - 这是 `agent_server_new`
- 下单执行与对账
  - 这是 `execution_service`

## 输入与输出

### 输入

当前主输入：

- `feature_service` 提供的 `raw_market_structure`

未来可扩展输入（仅限结构相关）：

- `feature_snapshot`（结构类特征）
- `selected_event`（结构类事件）
- `active_events`（结构类事件）

### 输出

输出给 `agent_server_new`：

- `MSL`
- `msl_bundle`（`short_term/mid_term/long_term`）
- `cross_horizon`（周期一致性与冲突摘要）
- `state_features`
- `anomaly_flags`

## 服务接口

当前最小接口：

- `GET /internal/market-state/healthz`
- `GET /internal/market-state/{exchange}/{symbol}`

返回体包含：

- `exchange`
- `symbol`
- `status`（新增：`ok` 或 `data_unavailable`）
- `msl`
- `msl_meta`（新增：schema/inference 元信息）
- `msl_bundle` / `msl_bundle_meta`（新增：多周期状态与元信息）
- `cross_horizon`（新增：跨周期一致性/冲突）
- `state_features`
- `anomaly_flags`
- `raw_market_structure`
- `reason_code` / `degraded_reasons`（仅在 `data_unavailable` 场景）

## 目录说明

```text
market_state_engine/
  README.md
  app.py
  main.py
  routes.py
  service.py
  contracts.py
  engine.py
  msl.py
  config/
    state_inference_profiles.json
  state_inference/
    base.py
    views.py
    rule_regime_inference.py
    positioning_inference.py
    volatility_inference.py
    liquidity_inference.py
    risk_inference.py
    structure_inference.py
    state_fusion.py
    msl_generator.py
    msl_generator_v1.py
    msl_generator_v2.py
    engine.py
  text/
    test_market_state_data_unavailable.py
  docs/
    api.md
    boundaries.md
    migration.md
  ports/
    raw_structure_provider.py
    storage/
      feature_store.py
  adapters/
    raw_structure_http.py
    in_memory_feature_store.py
```

## 与相邻服务的边界

### 对 `feature_service`

`market_state_engine` 只通过 provider / HTTP adapter 读取标准化结构，不反向依赖 `feature_service` 内部实现。

当前正式对接路径：

- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

上游不可用处理（新增）：

- 当 `feature_service` 返回 `503 feature_data_unavailable` 时，`market_state_engine` 会短路状态推断
- 接口返回 `200`，但 `status=data_unavailable`
- 下游可据此快速识别“数据不可用”而不是“中性状态”

### 对 `agent_server_new`

`market_state_engine` 只输出状态层 contract，不输出交易动作。

`agent_server_new` 应只消费：

- `MSL`
- `state_features`
- `anomaly_flags`

而不应直接读取 feature 层原始结构。

## 当前阶段

当前已经完成：

- 独立目录
- 独立 contract
- 独立服务骨架
- HTTP raw structure provider
- 正常分支与短路分支统一状态语义（`status=ok` / `status=data_unavailable`）
- 已补充跨服务契约测试（`feature_service -> market_state_engine`）覆盖
  - 新契约解析：`meta + data.raw_market_structure`
  - 上游 503 映射：`feature_data_unavailable -> data_unavailable`
- 已收口 MSL 契约为“结构状态专用”
  - `msl` 不再输出 `sentiment_state`
  - 状态层只保留结构相关状态字段（regime/liquidity/positioning/volatility/risk/structure）
- 已增加输入域守卫（结构边界防漂移）
  - `service.py` 会忽略 `news/social/onchain` 等外部事件输入字段
  - 当发现并忽略外部字段时，会附加 `anomaly_flags=external_event_input_ignored`
  - `state_features.evidence.ignored_external_input_keys` 记录被忽略字段
- 已完成引擎因子拆层
  - `engine.py` 的状态推断已拆到 `factors/`（`regime/liquidity/positioning/volatility/risk/structure`）
  - 拆层后输出契约保持不变，状态层回归测试通过
- 已新增状态层 CI 守卫脚本
  - `scripts/check_market_state_engine_guard.sh`
  - 默认检查 `sentiment_state` 不回归，并执行状态层契约测试（含插件流水线测试）
- 已新增 MSL 字段白名单守卫
  - `test_msl_contract_whitelist.py` 锁定 `msl` 字段集合（`ok` / `data_unavailable` 两条分支）
  - 守卫脚本默认执行该测试，防止契约字段漂移
- 已新增 `state->agent` 联动守卫脚本
  - `scripts/check_state_to_agent_contract_guard.sh`
  - 同时检查状态层与决策层核心实现不回归 `sentiment_state`，并执行跨模块契约测试
- 已新增新架构守卫总入口脚本
  - `scripts/check_new_arch_guards.sh`
  - 一次执行 feature/state/state->agent 全量契约守卫
- 已完成插件式状态推断流水线
  - `engine.py` 已接入 `state_inference/engine.py`
  - 默认推断链路为 `regime -> positioning -> volatility -> liquidity -> risk -> structure`
  - `risk_only` 已收敛为最小链路 `regime -> risk`
  - `state_fusion` 负责融合 partial state 与插件 warnings
  - `msl_generator` 负责将融合状态映射为稳定 `MSL` 输出
  - 支持多版本推断生成器（同一 schema）
    - `msl_generator_v1`
    - `msl_generator_v2`
    - 统一输出 `MSL schema v2`
  - 通过 `msl_meta` 输出 `schema_version/inference_version/inference_profile`
  - 已支持多周期状态并存输出（`msl_bundle`）
    - `short_term`
    - `mid_term`
    - `long_term`
  - 已支持跨周期冲突输出（`cross_horizon`）
    - `alignment`: `aligned|mixed|conflicting|unknown`
    - `conflicts`: 结构化冲突列表
    - 冲突字段覆盖：`trend`、`phase`、`volatility_regime`、`liquidity_risk`
    - 冲突排序优先级：`trend > phase > volatility_regime > liquidity_risk`
    - 新增执行建议字段：
      - `suggested_policy`: `follow_long_term|wait_confirmation|reduce_risk|no_action`
      - `policy_reason`: 规则命中原因（如 `short_long_trend_conflict`）
  - 已补充插件流水线测试（默认链路 + 插件异常降级 warning）
  - 已支持插件启停配置（默认全启用）
    - `MSE_STATE_PLUGIN_PROFILE`：预设链路（`default` / `fast_mode` / `risk_only`）
    - `MSE_STATE_PLUGIN_PROFILES_FILE`：profile 配置文件路径（JSON）
    - `MSE_MSL_INFERENCE_VERSION`：推断生成器版本（`msl_generator_v1` / `msl_generator_v2`）
    - `MSE_STATE_PLUGINS_ENABLED`：仅启用名单（逗号分隔）
    - `MSE_STATE_PLUGINS_DISABLED`：禁用名单（逗号分隔）
    - 优先级：`enabled_plugins` > `plugin_profile` > `default`，最后应用 `disabled_plugins`
    - profile 来源优先级：`profiles_file` > 内置默认配置
- 已补充服务层环境变量配置解析测试
- 已新增 `selected_event` 可选接入（Redis）
  - 新增端口：`ports/selected_event_provider.py`
  - 新增适配器：`adapters/selected_events_redis.py`
  - `service.py` 可选融合 selected_event 摘要到 `state_features.evidence`
  - 读取失败降级策略：不抛错，追加 `anomaly_flags=selected_events_unavailable`
  - 读取成功标记：`anomaly_flags=selected_event_context_attached`
  - `app.py` 支持环境变量装配：
    - `MSE_SELECTED_EVENT_PROVIDER_MODE=none|redis`
    - `MSE_SELECTED_EVENT_REDIS_URL`
    - `MSE_SELECTED_EVENT_STREAM`（默认 `ec:selected`）
    - `MSE_SELECTED_EVENT_LIMIT_DEFAULT`（默认 `20`）
    - `MSE_SELECTED_EVENT_SCAN_FACTOR`（默认 `5`）

当前仍是过渡阶段：

- 输入主要还是 `raw_market_structure`
- selected_event 已支持可选接入（Redis），默认仍为关闭模式（`none`）
- 尚未形成更完整的 state cache / replay 机制

## 下一步建议

优先实现顺序：

1. 固定 `raw_market_structure` schema
2. 让 `feature_service` 真实产出该结构
3. 再引入 `feature_snapshot`
4. 将 `selected_event` 从可选接入推进为默认生产路径，并补全 state->agent 实流联调
5. 最后稳定 MSL schema 与版本演进策略
