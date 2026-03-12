# feature_service

项目级新架构总览：`/docs/ARCHITECTURE_NEW.md`

`feature_service` 是目标架构中的 **Feature Layer**，位于 `data_server` 之后、`event_center_new` 和 `market_state_engine` 之前。

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

`feature_service` 的职责不是采集原始数据，也不是产出交易决策，而是把原始数据加工为可复用的结构化特征。

一句话定义：

> `feature_service` 负责把 market data 变成 feature data。

## 核心职责

`feature_service` 只负责以下能力：

- indicators
  - EMA / RSI / MACD / KDJ / MFI / MA / BollingerBand / Williams
- derived metrics
  - volatility burst
  - funding extreme
  - open interest delta
  - orderbook imbalance
  - liquidation density
- structure snapshots
  - multi-timeframe structure
  - trend memory
  - participant positioning
  - liquidity structure
  - support / resistance candidates
- feature normalization
  - 统一字段语义
  - 统一时间戳与版本
  - 统一 symbol / exchange / timeframe 表达
- feature serving
  - 对 `event_center_new` 输出“事件化特征输入”
  - 对 `market_state_engine` 输出“原始结构快照 / 特征集合”

## 不负责的事情

`feature_service` 不负责：

- 原始数据采集
  - 这是 `data_server`
- 事件去重、分类、优先级
  - 这是 `event_center_new`
- regime detection / anomaly synthesis / MSL generation
  - 这是 `market_state_engine`
- signal evaluation / strategy planning / risk gating
  - 这是 `agent_server_new`
- order routing / exchange execution / reconciliation
  - 这是 `execution_service`

## 输入与输出

### 输入

来自 `data_server` 的原始输入：

- kline
- ticker / mark price
- orderbook / depth
- open interest
- funding
- long-short ratios
- liquidation feed
- news / social / onchain raw feeds（未来）

### 未来扩展方向（多源特征收口）

`feature_service` 未来需要逐步接入新闻、社交、链上等数据源的特征输出，并继续作为统一特征出口服务：

- 新闻/舆情特征：情绪分、事件强度、主题标签、时效衰减
- 链上特征：资金流向、交易所净流入/流出、大额地址行为、活跃度
- 其他补充特征：按下游策略需求扩展，但统一走 `feature_service` 契约输出

落地原则：

1. 下游优先消费 `feature_service` 标准接口，不直接读取多源原始数据。
2. 新特征先定义统一 schema（`source/timestamp/confidence/freshness/degraded`）再接入。
3. 采用分阶段接入：先低频摘要特征，再逐步引入高频高噪声特征。

### 输出

对下游输出两类内容：

1. `FeatureSnapshot`
   - 给 `market_state_engine`
   - 用于状态推断
2. `FeatureEventCandidate`
   - 给 `event_center_new`
   - 用于事件化处理

### 推荐的稳定输出

- `GET /internal/feature-service/features/{exchange}/{symbol}`
  - 返回完整 feature snapshot
- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
  - 返回标准化 raw market structure

## 与相邻服务的边界

### 对 `data_server`

`feature_service` 只消费原始市场数据，不反向要求 `data_server` 理解 feature 语义。

### 对 `event_center_new`

`feature_service` 提供“可事件化的 feature 输入”，但不直接产出最终事件。

例如：

- `indicator_cross`
- `volatility_expansion`
- `funding_extreme`
- `oi_spike`

这些只是候选输入，不是事件中心的最终输出。

### 对 `market_state_engine`

`feature_service` 提供：

- `raw_market_structure`
- `feature_snapshot`
- `timeframe_features`

`market_state_engine` 再基于这些内容做：

- anomaly synthesis
- regime detection
- summary
- MSL generation

## 建议承接的现有能力

未来从现有代码迁移的重点来源：

- `data_server/binance/rest_binance/app/signals/*`
- `agent_server/agent_context/market_structure/*`
- 当前旧链路中用于拼 `market_structure` 的聚合逻辑

建议迁移策略：

1. 先迁指标计算
2. 再迁结构聚合
3. 最后替换旧的过渡实现

## 当前服务目录

```text
feature_service/
  README.md
  app.py
  main.py
  routes.py
  service.py
  contracts.py
  text/
    test_feature_service_normalizer.py
    test_feature_service_providers.py
    test_feature_service_routes_contract.py
    test_feature_service_redis_ethusdt.py
  docs/
    api.md
    boundaries.md
    migration.md
  ports/
    orderbook_provider.py
    open_interest_provider.py
    horizons_provider.py
    behavior_provider.py
    indicators_provider.py
  providers/
    __init__.py
    bundle.py
    noop.py
```

## 模块文档

- 模块级独立说明与迭代建议：`feature_service/docs/modules/index.md`
- 重构完成态总览（主要功能 + 下游输出）：`feature_service/docs/refactor-overview.md`
- 未来数据源预留骨架说明：`feature_service/docs/modules/future-sources.md`

## 当前阶段目标

当前目录中的实现目标不是一次性做完全部 feature 计算，而是先固定：

- 服务边界
- HTTP 接口
- feature contract
- 与 `market_state_engine` 的对接方式

当前过渡实现已经改为：

- `feature_service` 自己负责组装 `raw_market_structure`
- 底层 `orderbook / open_interest / horizons / behavioral` 默认使用 `services/feature_service/src/providers/market_structure_migrated` 本地迁移实现（`feature_service/providers/market_structure_migrated` 为兼容副本）
- 基础 `indicators` 已通过 Redis provider 直接读取 `data_server` 产出
- `derived_metrics` 已开始在本层汇总为稳定摘要特征
  - `indicator_metrics`
  - `horizon_metrics`
  - `orderbook_metrics`
  - `open_interest_metrics`
  - `behavior_metrics`
  - `pre_decision_metrics`
- 不再直接调用旧的最终 market structure 聚合器

## 下一步建议

优先实现顺序：

1. 固定 `raw_market_structure` schema
2. 实现 `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`
3. 实现 `GET /internal/feature-service/features/{exchange}/{symbol}`
4. 把 `market_state_engine` 的 HTTP raw structure adapter 接到这个服务
5. 再逐步迁移真实计算逻辑

## 当前对接约定

`market_state_engine` 当前会优先通过以下接口读取 raw structure：

- `GET /internal/feature-service/raw-structure/{exchange}/{symbol}`

因此这个接口应视为优先稳定的内部契约。

## 独立运行装配

`feature_service` 现在支持通过 `providers` 注入独立组装，不需要直接 import `agent_server`。

示例：

```python
from feature_service.providers import build_independent_provider_bundle
from feature_service.service import FeatureService

bundle = build_independent_provider_bundle()
service = FeatureService.from_bundle(bundle)
```

说明：

- `build_independent_provider_bundle()` 默认优先使用迁移版结构 provider（已本地化到 `services/feature_service/src/providers/market_structure_migrated`）
- 结构 provider 在运行异常时会自动降级到静态 provider，避免服务不可用
- 如果指标读取依赖不可用，会自动回退到 Noop 指标 provider，保证服务仍可启动
- `app.py` 仅使用独立装配路径（`build_independent_provider_bundle`）

## 重构执行状态

- 已完成 Task 1：新增 `providers` 注入层基础能力
  - `ProviderBundle`：统一注入 `Behavior/Horizons/OpenInterest/Orderbook/Indicators` 五类 provider
  - Noop providers：用于独立运行模式下的最小可启动装配（不依赖 `agent_server`）
- 已完成 Task 2：`FeatureService` 新增 `from_bundle` 构建入口，并在初始化时执行 provider 方法存在性校验
- 已完成 Task 3：新增 `providers/indicators_provider.py`，指标周期改为 `feature_service` 本地配置（`DEFAULT_INDICATOR_PERIODS`）
- 已完成 Task 4：新增 `providers/static_structure_providers.py`，提供四类结构 provider 的静态占位实现，支持纯注入运行
- 已完成 Task 5：新增 `build_independent_provider_bundle`，默认通过 `providers` 装配并避免 `agent_server` 依赖
- 已完成 Task 6：README 目录与运行方式已同步到新的 provider 注入架构
- 已完成 Task 7：完成最小自检（`build_independent_provider_bundle` + `FeatureService.from_bundle` 实例化成功）
- 已完成 Task 8：新增第二阶段任务组，开始切换 `app.py` 默认装配到独立模式
- 已完成 Task 9：`app.py` 默认切换到 `build_independent_provider_bundle` + `FeatureService.from_bundle`
- 已完成 Task 10：启动装配切换已完成，运行路径统一为独立 provider 注入
- 已完成 Task 11：最小启动链路自检通过（`from feature_service.app import create_app; create_app()`）
- 已完成 Task 12：启动第三阶段，开始用旧 `market_structure` 逻辑迁移替代静态伪 provider
- 已完成 Task 13：新增 `providers/migrated_structure_providers.py`，落地四类迁移版结构 provider
- 已完成 Task 14：`build_independent_provider_bundle` 默认注入迁移版结构 provider，运行失败自动降级静态 provider
- 已完成 Task 15：最小功能链路自检通过（`FeatureService.from_bundle(...).get_raw_structure(...)` 返回有效结构）
- 已完成 Task 16：启动第四阶段，目标是移除 `feature_service` 运行时对 `agent_server` 的 import 依赖
- 已完成 Task 17：复制旧 `market_structure` 到 `providers/market_structure_migrated` 并建立本地 redis helper
- 已完成 Task 18：迁移目录 import 已批量改为 `feature_service` 内部引用
- 已完成 Task 19：迁移 provider 入口改为本地模块并通过最小功能链路自检
- 已完成 Task 20：provider 实现已去除 `agent_server` 运行时 import（当前主实现路径：`services/feature_service/src/providers`）
- 已完成 Task 21：为 provider 降级路径增加日志（fallback 触发点与指标 provider 回退）
- 已完成 Task 22：新增 provider 降级行为测试（primary 异常时 fallback 生效）
- 已完成 Task 23：新增 `get_raw_structure`/`get_features` 输出契约测试
- 已完成 Task 24：新增测试通过（`pytest -q tests/test_feature_service_providers.py`）
- 已完成 Task 25：日志已统一中文，关键降级路径补充中文注释
- 已完成 Task 26：新增 Redis 集成测试 `tests/test_feature_service_redis_ethusdt.py`
- 已完成 Task 27：使用本地 Redis 数据完成 `binance/ETHUSDT` 集成验证（1 passed）
- 补充：新增 `pytest.ini` 注册 `integration` 标记，消除 UnknownMarkWarning
- 已完成 Task 28：新增版本化响应契约（`contracts.py`：`meta + data`，含 `schema_version`/`degraded`）
- 已完成 Task 29：`routes.py` 已按标准契约返回，`raw-structure/features` 统一为 `meta + data`
- 已完成 Task 30：新增路由契约测试，并同步下游 `market_state_engine` HTTP adapter 兼容新契约
- 已完成 Task 31：第七阶段测试通过（`test_feature_service_providers`/`test_feature_service_routes_contract`/`test_feature_service_redis_ethusdt`）
- 已完成 Task 32：新增请求级降级状态收集器，并在 fallback provider 记录降级原因
- 已完成 Task 33：`service/routes` 已透传 `degraded/degraded_reasons` 到标准响应 `meta`
- 已完成 Task 34：降级元信息链路测试通过（单元 + 路由契约 + Redis 集成）
- 已完成 Task 35：新增 `normalizers` 模块，统一 exchange/symbol、horizons、结构字段与降级原因格式
- 已完成 Task 36：`service.py` 已在响应前接入 normalizer，输出稳定的标准结构
- 已完成 Task 37：新增 `test_feature_service_normalizer.py` 并通过单元+契约+Redis 集成验证
- 已完成 Task 38：标准化层落地状态已同步到 `TASKS.md` 与 `README.md`
- 已完成 Task 39：`service.py` 新增关键结构不可用判定与业务异常（`FeatureDataUnavailableError`）
- 已完成 Task 40：`routes.py` 已将该异常映射为 `503`，错误码 `feature_data_unavailable`
- 已完成 Task 41：硬失败路径测试通过（单元 + 路由契约 + Redis 集成）
- 已完成 Task 42：硬失败策略与下游错误码对接约定已同步文档
- 已完成 Task 43：`docs/api.md` 已冻结到当前标准契约（`meta + data`）
- 已完成 Task 44：API 文档补充了 503 错误体、`degraded_reasons` 语义与下游兼容建议
- 已完成 Task 45：契约冻结文档状态已同步到 `TASKS.md` 与 `README.md`
- 已完成 Task 46：`contracts.py` 已升级为关键字段强类型契约（raw/features 核心结构）
- 已完成 Task 47：契约相关测试与 Redis 集成测试回归通过
- 已完成 Task 48：强类型契约完成状态已同步到 `TASKS.md` 与 `README.md`
- 已完成 Task 54：范围收口，`agent_server` 属于旧链路，不再作为 `feature_service` 重构验收项
- 已完成 Task 55：清理迁移脚本模式路径探测，不再查找 `agent_server/agent_context`
- 已完成 Task 56：清理迁移层旧注释文案，统一为 `feature_service` 本地迁移语义
- 已完成 Task 57：`feature_service/text` 回归测试通过，确认本次清理不影响功能
- 已完成 Task 58：冻结 `RawStructureResponse/FeatureResponse` JSON Schema 到 `feature_service/docs/schemas/`
- 已完成 Task 59：新增 schema 守卫测试，确保代码模型与冻结 schema 一致
- 已完成 Task 60：加强路由契约测试，显式禁止旧顶层字段（`raw_market_structure`/`features`）回归
- 已完成 Task 61：新增 `scripts/check_feature_service_schema_guard.sh`（schema 文件存在性 + 契约守卫测试）
- 已完成 Task 62：守卫脚本本地执行通过，可直接接入 CI
- 已完成 Task 63：项目级文档入口已纳入 feature schema 守卫脚本

## 错误码约定（新增）

当关键结构数据（`orderbook/open_interest/horizons/behavioral`）同时不可用时：

- 接口返回 `HTTP 503`
- `detail.code = "feature_data_unavailable"`
- `detail.degraded_reasons` 包含降级链路原因，供下游熔断/重试策略使用
