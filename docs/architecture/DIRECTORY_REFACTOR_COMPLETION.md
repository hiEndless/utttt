# Directory Refactor Completion Report

更新时间：2026-03-12  
范围：目录重构（services/contracts/verification/fixtures/tools/docs）与脚本入口收敛

## 1. Executive Status

- 目录骨架目标已达成：`project/` 目标结构已落地并由结构守卫持续检查。
- 业务服务迁移目标已达成：`services/services_map.yaml` 标记 5/5 服务为 `fully_migrated_no_legacy_wrappers`。
- 脚本收敛目标已达成：`scripts/*` 中“非 hard-pinned 且非白名单 wrapper 的实逻辑脚本”当前为 `0`。

## 2. Progress Snapshot

基于 `verification/guards/script_compat_whitelist.yaml`：

- workflow hard-pinned：5
- snapshot/help hard-pinned：3
- text wiring hard-pinned：2
- hard-pinned 唯一路径总计：8
- compatibility wrappers retained：35

结论：脚本层已进入“兼容窗口治理阶段”，不再是“迁移实施阶段”。

## 3. Remaining Hard-Pinned Scripts

以下脚本暂不建议删除或改名（路径稳定性仍被 CI/workflow/snapshot/wiring 依赖）：

1. `scripts/check_new_arch_guards.sh`
2. `scripts/check_event_center_contract_guards.sh`
3. `scripts/check_market_state_engine_guard.sh`
4. `scripts/ci_event_center_quick_strict.sh`
5. `scripts/ci_event_center_quick_lenient.sh`
6. `scripts/ci_event_center_full_strict.sh`
7. `scripts/ci_event_center_emit_meta_header.sh`
8. `scripts/check_contract_docs_index_guard.sh`

说明：完整原因与分类以机器清单为准：`verification/guards/script_compat_whitelist.yaml`。

## 4. Gap To Final End-State

距“最终可移除大部分 scripts 兼容壳”的差距主要在三类依赖：

1. Workflow path pinning  
2. Help/snapshot pinning  
3. Text source wiring guard pinning

这些是治理问题，不是目录重构本体问题。

## 5. Next Actions (Recommended)

1. 将 workflow 中 `scripts/*` 调用切换为 `tools/ci/*` 与 `tools/local/*`。  
2. 将 help/snapshot 守卫改为对 `tools/*` 入口做快照，再刷新 snapshot。  
3. 将 text wiring 守卫从“脚本文本扫描”改为“命令意图检查/语义检查”。  
4. 完成以上三步后，按批次删除 `scripts/*` compatibility wrappers。

## 6. Validation Commands

1. `bash tools/local/check_structure.sh`
2. `bash tools/local/check_script_compat_whitelist.sh`
3. `bash tools/ci/new_arch_guards_full.sh`
4. `bash tools/ci/verify_quick.sh`
