# Release Summary 2026-03-12

更新时间：2026-03-12

统一门禁模板：`docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md`

## 1. 发布标识

- 分支：`master`
- 基线 tag：`refactor-guard-baseline-20260312`
- 基线 commit：以命令结果为准（`git rev-parse --short refactor-guard-baseline-20260312`）

## 2. 本轮核心变更

1. contract/entry guard 对齐
- 新增并接入 `event_center` 合同入口守卫。
- feature/state/execution/event_center 四服务入口守卫拓扑对齐。

2. 版本联动与反漂移
- 引入并强化 `contract_change_bundle_guard`：
  - 支持 `event_center_runtime_config_version` 版本锚点联动四件套校验。
  - 新增 `--show-detected-versions` 调试输出。
- docs bundle 与 verify_quick 失败路径自动给出（并执行）标准排障命令。

3. execution 破坏性变更升版
- `execution-schema-mapping` 从 `v15` 升至 `v16`。
- 同步 code/schema/manifest/CONTRACT_INDEX/docs/tests。

4. 文档与运行手册收敛
- 统一 operations 文档中的标准排障文案。
- 增加 baseline 记录与索引入口。

5. event_center CI 可观测增强
- quick/full 入口统一输出 `[CI_GUARD]` 摘要行（guard mode / wiring / runtime 开关）。
- CI 失败 artifact 产出独立摘要文件：
  - `guard_summary.quick_strict.log`
  - `guard_summary.quick_lenient.log`
  - `guard_summary.full.log`
- workflow 失败提示新增摘要查看命令，支持首屏定位配置门禁问题。

6. agent readyz 门禁上线（分层收敛）
- quick：新增可选观测开关 `WITH_AGENT_READYZ=1`（默认关闭，不影响主链路时延）。
- regression：默认接入 readyz 聚合门禁（`MAX_AGENT_READYZ_LEVEL=red`，`REQUIRE_AGENT_READYZ_REPORT=1`）。
- nightly：默认接入更严格 readyz 门禁（`MAX_AGENT_READYZ_LEVEL=yellow`，`REQUIRE_AGENT_READYZ_REPORT=1`）。
- 聚合报告新增 readyz 字段用于发布核对：`agent_readyz_status_level`、`agent_readyz_report_count`、`agent_readyz_error_count`、`agent_readyz_errors`。

## 3. 关键验证结果

- `bash tools/ci/verify_quick.sh` -> pass
- `WITH_AGENT_READYZ=1 bash tools/ci/verify_quick.sh` -> pass（可选观测链路）
- `bash tools/ci/verify_regression.sh` -> pass（默认 readyz 门禁链路）
- `bash tools/ci/verify_nightly.sh` -> pass（默认 readyz + confidence 门禁链路）
- `bash tools/ci/new_arch_guards_full.sh --quick` -> pass
- `bash tools/local/check_docs_contracts_bundle.sh` -> pass
- `bash tools/local/check_contract_docs_index_guard.sh` -> pass
- `bash tools/local/check_release_ready.sh` -> pass

## 4. 标准排障命令

```bash
bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions
rg -n "^\[CI_GUARD\]" quick_strict.log quick_lenient.log full_guard.log
cat guard_summary.quick_strict.log guard_summary.quick_lenient.log guard_summary.full.log
```

## 5. 回滚建议

如需快速回滚到封板前稳定点，优先基于 tag 检出：

```bash
git checkout refactor-guard-baseline-20260312
```

如需回滚单模块，建议按服务维度回滚并重跑以下最小验证：

```bash
bash tools/local/check_docs_contracts_bundle.sh
bash tools/local/check_execution_breaking_version_bump_guard.sh
```

## 6. 发布排障最小复现（release gate schema）

```bash
git checkout -b tmp/release-gate-schema-repro
echo "// repro" >> verification/reports/release_gate_summary_v1.schema.json
bash tools/local/check_contract_change_bundle_guard.sh
```

预期：守卫提示 schema 变更触发四件套，需同步更新索引/契约文档/运行说明/守卫测试。
