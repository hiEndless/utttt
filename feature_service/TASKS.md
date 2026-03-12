# feature_service 重构任务

- [x] Task 1: 创建 `providers` 注入层基础（`ProviderBundle` + Noop providers），确保服务组装只依赖 `ports`。
- [x] Task 2: 在 `service.py` 增加 `from_bundle` 构建入口与 provider 运行时校验，统一注入方式。
- [x] Task 3: 在 `providers` 内实现本地 `IndicatorsProvider`（含本地周期配置），避免依赖旧服务常量。
- [x] Task 4: 在 `providers` 内实现 `Orderbook/Horizons/OpenInterest/Behavior` provider 占位实现与组合工厂。
- [x] Task 5: 提供 `independent` 组装函数（独立运行模式），默认不依赖 `agent_server`。
- [x] Task 6: 更新 `README.md` 的目录与启动说明，记录新注入架构与迁移状态。
- [x] Task 7: 完成最小自检（导入与实例化链路），并在文档中记录验证结果。

## 启动装配切换任务（第二阶段）

- [x] Task 8: 新增第二阶段任务组，聚焦 `app.py` 默认独立运行装配切换。
- [x] Task 9: 修改 `app.py`，默认走 `build_independent_provider_bundle` + `FeatureService.from_bundle`。
- [x] Task 10: 启动装配迁移期兼容开关已下线，`app.py` 统一为独立 provider 注入路径。
- [x] Task 11: 运行最小启动链路自检并同步更新 `README.md` 状态说明。

## 旧 market_structure 迁移任务（第三阶段）

- [x] Task 12: 新增第三阶段任务组，目标是用迁移版结构 provider 替代静态伪实现。
- [x] Task 13: 在 `feature_service/providers` 实现迁移版 `Orderbook/OpenInterest/Horizons/Behavior` provider。
- [x] Task 14: 调整 `build_independent_provider_bundle` 默认注入迁移版 provider，失败时降级静态 provider。
- [x] Task 15: 更新 `README.md`（迁移来源、默认注入策略、降级行为）并完成最小链路自检。

## 去除 agent_server 运行时依赖（第四阶段）

- [x] Task 16: 新增第四阶段任务组，目标是迁移代码本地化并移除 `agent_server` 运行时 import。
- [x] Task 17: 复制 `market_structure` 核心模块到 `feature_service/providers/market_structure_migrated` 并建立本地 redis 工具。
- [x] Task 18: 批量修正迁移模块 import 路径，确保仅引用 `feature_service` 内部模块。
- [x] Task 19: 调整 `migrated_structure_providers.py` 指向本地迁移模块并完成最小功能自检。
- [x] Task 20: 更新 `README.md` 与 `TASKS.md` 状态，记录“已移除运行时 agent_server import”。 

## 可观测性与契约测试（第五阶段）

- [x] Task 21: 为 fallback provider 与独立 bundle 增加降级日志，便于排查迁移路径稳定性。
- [x] Task 22: 新增 `feature_service` provider 降级行为测试（primary 失败 -> fallback 生效）。
- [x] Task 23: 新增 `feature_service` 输出契约测试（`get_raw_structure`/`get_features` 关键字段稳定）。
- [x] Task 24: 运行新增测试并同步 `README.md`/`TASKS.md` 状态。

## Redis 实数集成验证（第六阶段）

- [x] Task 25: 日志文案统一中文并补充关键中文注释。
- [x] Task 26: 新增基于 Redis 的 `binance/ETHUSDT` 集成测试。
- [x] Task 27: 执行 Redis 集成测试并回写 `README.md`/`TASKS.md` 结果。

## 标准输出契约（第七阶段）

- [x] Task 28: 在 `contracts.py` 定义版本化响应契约（`meta + data`）与统一字段。
- [x] Task 29: 更新 `routes.py` 按标准契约返回 `raw-structure` 与 `features`。
- [x] Task 30: 更新测试用例适配新契约（单元 + Redis 集成）。
- [x] Task 31: 运行测试并同步 `README.md`/`TASKS.md` 状态。

## 降级元信息接入（第八阶段）

- [x] Task 32: 新增请求级降级状态收集器，并在 fallback provider 中记录 `degraded_reasons`。
- [x] Task 33: `service -> routes` 透传 `degraded/degraded_reasons` 到响应 `meta`。
- [x] Task 34: 补充并通过测试（provider 降级测试 + 路由契约测试 + Redis 集成测试）。

## 标准化层接入（第九阶段）

- [x] Task 35: 新增 `normalizers` 模块，统一标准化 raw/features 输出结构。
- [x] Task 36: 在 `service.py` 接入 normalizer，响应前统一做字段归一化。
- [x] Task 37: 新增 normalizer 测试并执行全量相关测试（单元 + Redis 集成）。
- [x] Task 38: 更新 `README.md`/`TASKS.md` 记录标准化层落地结果。

## 硬失败策略（第十阶段）

- [x] Task 39: 在 `service.py` 增加“关键结构数据不可用”判定与业务异常类型。
- [x] Task 40: 在 `routes.py` 将该异常映射为 503 标准错误响应（含 `degraded_reasons`）。
- [x] Task 41: 补充测试覆盖硬失败路径，并回归单元/契约/Redis 集成测试。
- [x] Task 42: 更新 `README.md`/`TASKS.md`，记录硬失败策略与下游对接约定。

## 契约冻结文档（第十一阶段）

- [x] Task 43: 更新 `feature_service/docs/api.md` 为当前标准契约（`meta + data`）。
- [x] Task 44: 在 API 文档中补充 503 错误体、`degraded_reasons` 语义、下游兼容建议。
- [x] Task 45: 同步更新 `README.md`/`TASKS.md`，标记契约冻结文档完成。

## 强类型契约收口（第十二阶段）

- [x] Task 46: 将 `contracts.py` 升级为关键字段强类型模型（raw/features 结构核心字段）。
- [x] Task 47: 运行契约相关测试，验证 routes 与下游兼容性不回归。
- [x] Task 48: 更新 `README.md`/`TASKS.md` 记录强类型契约完成状态。

## 测试与文档目录重组（第十三阶段）

- [x] Task 49: 将原根目录 `tests/` 测试迁移到对应模块下的 `text/` 目录（`feature_service/market_state_engine/event_center/agent_server`）。
- [x] Task 50: 修复迁移后的测试路径与导入问题（含 `feature_service` 根路径计算、`event_center` grading 导入）。
- [x] Task 51: 将根目录工程文档迁移到对应模块 `docs/`（已迁入 `agent_server_new/docs/`）。
- [x] Task 52: 更新 `pytest.ini` 使用模块级 `testpaths`，确保默认发现新目录。
- [x] Task 53: 更新 `feature_service/README.md` 与 `market_state_engine/README.md` 目录树，避免文档与代码结构不一致。
- [x] Task 54: 范围收口：`agent_server` 属于旧链路，不纳入 `feature_service` 重构验收项。

## 迁移痕迹清理（第十四阶段）

- [x] Task 55: 清理 `market_structure_migrated` 中脚本模式的旧路径探测（不再查找 `agent_server/agent_context`）。
- [x] Task 56: 统一迁移层中文注释表述，移除“从 agent_server 层获取 Redis 连接”等旧文案。
- [x] Task 57: 回归 `feature_service/text` 测试并同步 `README.md` / `TASKS.md` 状态。

## 契约强约束守卫（第十五阶段）

- [x] Task 58: 冻结 `RawStructureResponse/FeatureResponse` JSON Schema 到 `feature_service/docs/schemas/`。
- [x] Task 59: 新增 schema 守卫测试，确保代码模型与冻结 schema 文件一致。
- [x] Task 60: 加强路由契约测试，显式禁止旧顶层字段（`raw_market_structure`/`features`）回归。

## CI 守卫落地（第十六阶段）

- [x] Task 61: 新增 `scripts/check_feature_service_schema_guard.sh`，检查 schema 文件存在并执行契约守卫测试。
- [x] Task 62: 本地执行守卫脚本通过，确认可直接接入 CI。
- [x] Task 63: 同步更新项目导航文档入口，纳入 schema 守卫脚本。

## services canonical 路径收敛（第十七阶段）

- [x] Task 64: 将 `app/routes/service/contracts` 主实现迁入 `services/feature_service/src/`，旧路径改为兼容壳。
- [x] Task 65: 将 `providers` / `normalizers` / `ports` 主实现迁入 `services/feature_service/src/`，旧路径改为兼容壳。
- [x] Task 66: 将 `providers/market_structure_migrated` 镜像迁入 `services/feature_service/src/providers/market_structure_migrated/`。
- [x] Task 67: 旧 `feature_service/providers/market_structure_migrated/**/*.py` 基本改为兼容壳；保留 `behavioral/behavior_output.py` 旧路径猴子补丁兼容实现。
- [x] Task 68: 更新模块文档为 canonical 路径表达，并补充兼容壳路径说明。
- [x] Task 69: 新增兼容壳下线草案文档（`docs/operations/FEATURE_SERVICE_COMPAT_WRAPPER_DECOMMISSION.md`）。
- [x] Task 70: 新增旧路径 import 审计脚本（`tools/local/check_feature_legacy_imports.sh`）。
