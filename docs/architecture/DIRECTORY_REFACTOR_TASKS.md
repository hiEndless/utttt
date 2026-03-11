# Directory Refactor Tasks

更新时间：2026-03-12
负责人：UTaker
状态：in_progress

## 1. 目标

将“业务执行代码”与“验证/回放/契约治理代码”解耦，形成长期可复用目录架构：

- `services/`（已完成子目录骨架，运行路径仍兼容旧目录）
- `contracts/`
- `verification/`
- `fixtures/`
- `tools/`
- `docs/`

说明：当前采用“分阶段迁移”，优先保留现有路径兼容，不做一次性大搬迁。

## 2. 阶段计划

### Phase 1: 骨架与统一入口（已完成）

- [x] 创建目录骨架：`contracts/verification/fixtures/tools`
- [x] 建立注册清单：`contracts/registry.yaml`
- [x] 建立 suite 清单：`verification/suites.yaml`
- [x] 建立统一入口：`tools/ci/verify_all.sh`
- [x] 建立 guard 兼容层：`verification/guards/*.sh`
- [x] 增加机器可读报告：`verification/run_suite.sh --report-json`

验收：
- `bash tools/ci/verify_all.sh --quick` 通过。

### Phase 2: 路径收编（已完成）

- [x] 产出旧->新路径迁移映射（guard/suite/fixtures/contracts）
- [x] 增加本地开发快捷入口（quick/full/report）
- [x] 在文档中声明“新入口优先，旧入口兼容”
- [x] 梳理 scripts 分类并标注“待迁移/保留”
- [x] 文档目录分流到 `docs/architecture|contracts|operations`
- [x] 旧文档入口保留兼容跳转（避免立即破坏人工路径习惯）
- [x] 增加目录骨架合规脚本：`tools/local/check_structure.sh`

验收：
- 本地可仅通过 `tools/local/*` 完成常用验证流程。

### Phase 3: 资产迁移（进行中）

- [x] 将可复用 validator 从模块测试目录迁入 `verification/validators`
- [x] 将 replay 公共能力迁入 `verification/replay`
- [x] 将跨服务 contract fixture 显式化到 `fixtures/contract_cases`
- [x] 建立 `services/*` 五个业务服务迁移占位目录
- [x] 建立 `services/*` 软迁移统一入口（soft adapters，不搬业务源码）
- [x] 增加 `tools/local/run_*` 统一启动脚本（默认走 `python -m services.*`）
- [x] 核心架构文档切换为 `tools/local/run_*` 推荐启动命令
- [x] 完成首个物理迁移试点：`feature_service/main.py` 实现迁入 `services/feature_service/runtime/main.py`
- [x] 完成第二个物理迁移试点：`market_state_engine/main.py` 实现迁入 `services/market_state_engine/runtime/main.py`
- [x] 完成第三个物理迁移试点：`execution_service/main.py` 实现迁入 `services/execution_service/runtime/main.py`
- [x] 完成第四个物理迁移试点：`event_center_new/main.py` 实现迁入 `services/event_center_new/runtime/main.py`
- [x] 完成第五个物理迁移试点：`agent_server_new/runner.py` 实现迁入 `services/agent_server_new/runtime/runner.py`
- [x] 完成第六个物理迁移试点：`agent_server_new/pipeline_smoke.py` 与 `memory_summary_runner.py` 实现迁入 `services/agent_server_new/runtime/`
- [x] 完成第七个物理迁移试点：`event_center_new/replay_main.py` 实现迁入 `services/event_center_new/runtime/replay_main.py`
- [x] 完成第八个物理迁移试点：`feature_service/app.py` 实现迁入 `services/feature_service/src/app.py`
- [x] 完成第九个物理迁移试点：`feature_service/routes.py` 实现迁入 `services/feature_service/src/routes.py`
- [x] 完成第十个物理迁移试点：`feature_service/service.py` 实现迁入 `services/feature_service/src/service.py`
- [x] 完成第十一个物理迁移试点：`feature_service/contracts.py` 实现迁入 `services/feature_service/src/contracts.py`
- [x] 完成第十二个物理迁移试点：`feature_service/providers/{bundle,noop,degradation_state}.py` 实现迁入 `services/feature_service/src/providers/`
- [x] 完成第十三个物理迁移试点：`feature_service/providers/fallback_structure_providers.py` 实现迁入 `services/feature_service/src/providers/`
- [x] 完成第十四个物理迁移试点：`feature_service/providers/{static,migrated}_structure_providers.py` 实现迁入 `services/feature_service/src/providers/`
- [x] 增加 `services/services_map.yaml` 一致性检查并接入 `check_structure.sh`
- [x] 固化 services Phase-2 试点里程碑文档（`SERVICES_PHASE2_MILESTONE.md`）
- [x] 增加 registry 驱动的 contract 聚合索引同步（schemas/mappings）
- [x] 增加语义审计入口（`verification/auditors/semantic_contract_audit.py`）
- [x] 将 event_center CI 组合入口实现迁入 `tools/ci`（旧 `scripts/ci_event_center_*` 保留兼容转发）
- [x] 将 state/agent/event_center 三个核心 guard 实现迁入 `tools/local`（旧 `scripts/check_*` 保留兼容转发）
- [x] 将 contract docs index guard 实现迁入 `tools/local`（保留 help 快照守卫在 `scripts/`）
- [x] 将 `check_new_arch_guards.sh` 全量执行主体迁入 `tools/ci/new_arch_guards_full.sh`
- [x] 将 verification wrappers 直连 `tools/*` 实现层（减少 scripts 中间跳转）
- [x] 建立 `scripts/*` 兼容白名单与机器检查（workflow/snapshot/wiring hard-pinned）
- [x] 将脚本兼容白名单检查接入 nightly CI
- [x] 将脚本兼容白名单检查接入 regression CI（并使用 warning budget 替代 strict 语义检查）
- [x] 将脚本兼容白名单检查接入 quick CI（统一三条场景入口）
- [ ] 迁移后保留旧路径薄包装 1 个迭代周期
  - 兼容窗口文档：`VERIFICATION_COMPAT_WINDOW.md`（active）

验收：
- 验证能力可在不依赖业务服务源码路径的情况下独立运行。

### Phase 4: 监控服务化预留（进行中）

- [x] 输出统一报告 schema v2（含 git_sha/env/suite_tags）
- [x] 增加报告聚合脚本（按时间窗口汇总 pass/fail）
- [x] 预留 HTTP 查询接口定义（只读）
- [x] 对接告警阈值（失败率、退化率、schema 漂移）
- [x] 增加场景化 CI 入口（`tools/ci/verify_quick.sh|verify_regression.sh|verify_nightly.sh`）
- [x] semantic audit 报告并入聚合阈值检查链路（aggregate + thresholds）
- [x] semantic warning budget（按字段）并接入 nightly

当前进展补充：
- 已落地最小只读 API 文件后端实现（`verification/api`），用于查询 latest/list/summary/report。

验收：
- 验证结果可被外部监控系统直接消费。

## 3. 约束与原则

1. 不做破坏性大迁移；每阶段都必须保留旧入口可用。
2. 每次迁移必须可被 guard 覆盖并可回滚。
3. 先收编入口，再迁移资产；先可观测，再服务化。
4. 所有新增结构必须提供最小文档与示例命令。

## 4. 回滚策略

- 若新入口异常：回退到 `scripts/check_*` 直接执行路径。
- 若迁移导致 CI 不稳定：恢复旧路径调用并延期资产搬迁。

## 5. 当前下一步（本轮执行）

1. 逐步将 `scripts/check_*` 迁移为薄包装（指向 `tools/local` 与 `verification/*`）。
2. 收敛 root 文档兼容层，逐步切到 `docs/{architecture,contracts,operations}`。
3. 将 semantic warning budget 结果接入告警渠道（飞书/Slack/Webhook）。

## 6. 验收命令（当前）

1. `bash tools/local/check_structure.sh`
2. `bash tools/local/verify_quick.sh`
3. `bash tools/local/sync_contract_indexes.sh`
4. `bash tools/local/audit_semantics.sh`
5. `bash tools/ci/verify_quick.sh`
