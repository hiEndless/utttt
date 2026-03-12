# UTaker 项目协作约束（Codex）

本文件用于约束 Codex 在本仓库内的默认开发行为，目标是长期稳定迭代并最大限度防止字段契约漂移。

## 1. 工作目录与边界

- 新架构代码统一位于 `services/*`。
- 旧目录（如根目录历史模块）默认只读，除非任务明确要求迁移或清理。
- 所有跨服务契约以 `docs/CONTRACT_INDEX.md` 为唯一入口。

## 2. 变更执行流程（必须遵守）

每次任务按以下顺序执行：

1. 明确影响服务与契约文件。
2. 修改代码与测试/守卫。
3. 同步更新文档。
4. 运行对应 guard（至少模块 guard；跨服务改动跑 `tools/local/check_new_arch_guards.sh`）。
5. 单任务单提交（一个逻辑改动一个 commit）。

## 3. 契约变更四件套（强制）

当修改以下文件之一时视为“契约变更”：

- `services/*/docs/*.schema.json`
- `services/*/docs/schema_mapping.json`

必须同步更新四件套：

1. `docs/CONTRACT_INDEX.md`
2. 模块契约文档（如 `api.md` / `schema.md` / `runner_output_contract.md`）
3. 模块迁移文档（如 `migration.md` / `refactor.md` / `REFACTOR_PLAN_V2.md`）
4. 守卫或测试（`tools/local/check_*guard.sh` 或 `verification/*`）

守卫脚本：`tools/local/check_contract_change_bundle_guard.sh`

## 4. 版本与兼容策略

- 任何 breaking 变更（新增 required、删除字段、收紧 enum、语义变化）必须升版并写迁移说明。
- 新字段默认“先可选后必填”；跨服务推广至少经过一个迁移窗口。
- 禁止用“隐式 dict 字段”绕过 schema；跨服务字段必须先入契约文档再落代码。

## 5. 文档单源策略

- 架构总览 canonical：`docs/architecture/ARCHITECTURE_NEW.md`
- 契约速查 canonical：`docs/contracts/CONTRACTS_QUICK_REF.md`
- 根目录同名文档仅保留跳转，不写分叉内容。
- 修改守卫帮助输出时，必须同步快照与 runbook。

## 6. 守卫与验证

- 本地快速：`bash tools/local/verify_quick.sh`
- 全量守卫：`bash tools/local/check_new_arch_guards.sh`
- CI 全量入口：`bash tools/ci/new_arch_guards_full.sh`

若守卫失败，先修守卫暴露的问题，不允许跳过或绕过。

## 7. 提交规范

- commit message 使用模块前缀：`refactor(feature): ...`、`chore(guards): ...`。
- 不在一次提交中混入无关模块改动。
- 若改动契约，提交说明必须写明：影响服务、版本变化、迁移路径。
- 使用中文备注提交信息
