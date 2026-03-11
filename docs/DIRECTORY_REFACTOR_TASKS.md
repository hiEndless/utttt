# Directory Refactor Tasks

更新时间：2026-03-12
负责人：UTaker
状态：in_progress

## 1. 目标

将“业务执行代码”与“验证/回放/契约治理代码”解耦，形成长期可复用目录架构：

- `services/`（现阶段由各服务目录承担）
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

### Phase 2: 路径收编（进行中）

- [x] 产出旧->新路径迁移映射（guard/suite/fixtures/contracts）
- [x] 增加本地开发快捷入口（quick/full/report）
- [x] 在文档中声明“新入口优先，旧入口兼容”
- [x] 梳理 scripts 分类并标注“待迁移/保留”

验收：
- 本地可仅通过 `tools/local/*` 完成常用验证流程。

### Phase 3: 资产迁移（未开始）

- [x] 将可复用 validator 从模块测试目录迁入 `verification/validators`
- [ ] 将 replay 公共能力迁入 `verification/replay`
- [ ] 将跨服务 contract fixture 显式化到 `fixtures/contract_cases`
- [ ] 迁移后保留旧路径薄包装 1 个迭代周期

验收：
- 验证能力可在不依赖业务服务源码路径的情况下独立运行。

### Phase 4: 监控服务化预留（未开始）

- [ ] 输出统一报告 schema v2（含 git_sha/env/suite_tags）
- [ ] 增加报告聚合脚本（按时间窗口汇总 pass/fail）
- [ ] 预留 HTTP 查询接口定义（只读）
- [ ] 对接告警阈值（失败率、退化率、schema 漂移）

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

1. 进入 Phase 3：验证能力代码收编（validator/replay/fixtures）。
2. 在不破坏现有 CI 的前提下，增加按领域的细粒度 verification wrappers。
