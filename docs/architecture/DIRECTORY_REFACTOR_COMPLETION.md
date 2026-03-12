# Directory Refactor Completion Report

更新时间：2026-03-12  
范围：目录重构（services/contracts/verification/fixtures/tools/docs）与脚本入口收敛

## 1. Executive Status

- 目录骨架目标已达成：`project/` 目标结构已落地并由结构守卫持续检查。
- 业务服务迁移目标已达成：`services/services_map.yaml` 标记 5/5 服务为 `fully_migrated_no_legacy_wrappers`。
- 脚本收敛目标已达成：`scripts/*` 中“非 hard-pinned 且非白名单 wrapper 的实逻辑脚本”当前为 `0`。

## 2. Progress Snapshot

基于 `verification/guards/script_compat_whitelist.yaml`：

- workflow hard-pinned：1
- snapshot/help hard-pinned：0
- text wiring hard-pinned：1
- hard-pinned 唯一路径总计：1
- compatibility wrappers retained：41

结论：脚本层已进入“兼容窗口治理阶段”，不再是“迁移实施阶段”。

## 3. Remaining Hard-Pinned Scripts

以下脚本暂不建议删除或改名（路径稳定性仍被 CI/workflow/snapshot/wiring 依赖）：

1. `scripts/check_new_arch_guards.sh`

说明：完整原因与分类以机器清单为准：`verification/guards/script_compat_whitelist.yaml`。

## 4. Gap To Final End-State

距“最终可移除大部分 scripts 兼容壳”的差距主要在三类依赖：

1. Workflow path pinning  
2. Help/snapshot pinning  
3. Text source wiring guard pinning

这些是治理问题，不是目录重构本体问题。

## 5. Next Actions (Recommended)

1. 将 `check_new_arch_guards` 的 workflow 触发与 wiring 依赖切到 `tools/*` 入口。  
2. 完成后删除最后一个 hard-pinned 脚本并进入 wrapper 下线批次。

## 6. Validation Commands

1. `bash tools/local/check_structure.sh`
2. `bash tools/local/check_script_compat_whitelist.sh`
3. `bash tools/ci/new_arch_guards_full.sh`
4. `bash tools/ci/verify_quick.sh`
