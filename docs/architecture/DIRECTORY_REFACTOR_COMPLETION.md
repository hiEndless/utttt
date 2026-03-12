# Directory Refactor Completion Report

更新时间：2026-03-12  
范围：目录重构（services/contracts/verification/fixtures/tools/docs）与脚本入口收敛

## 1. Executive Status

- 目录骨架目标已达成：`project/` 目标结构已落地并由结构守卫持续检查。
- 业务服务迁移目标已达成：`services/services_map.yaml` 标记 5/5 服务为 `fully_migrated_no_legacy_wrappers`。
- 脚本收敛目标已达成：`scripts/*` 中“非 hard-pinned 且非白名单 wrapper 的实逻辑脚本”当前为 `0`。

## 2. Progress Snapshot

基于 `verification/guards/script_compat_whitelist.yaml`：

- workflow hard-pinned：0
- snapshot/help hard-pinned：0
- text wiring hard-pinned：0
- hard-pinned 唯一路径总计：0
- compatibility wrappers retained：0

结论：脚本层兼容治理已完成，`scripts/*` 兼容壳已清零。

## 3. Remaining Hard-Pinned Scripts

以下脚本暂不建议删除或改名（路径稳定性仍被 CI/workflow/snapshot/wiring 依赖）：

（无）

说明：完整原因与分类以机器清单为准：`verification/guards/script_compat_whitelist.yaml`。

## 4. Gap To Final End-State

已无脚本兼容壳与 hard-pinned 依赖差距。

## 5. Next Actions (Recommended)

1. 维持 `tools/*` 主入口稳定，禁止回退新增 `scripts/*` 依赖。  
2. 继续将历史文档中的 legacy 路径说明收敛为归档信息。

## 6. Validation Commands

1. `bash tools/local/check_structure.sh`
2. `bash tools/local/check_script_compat_whitelist.sh`
3. `bash tools/ci/new_arch_guards_full.sh`
4. `bash tools/ci/verify_quick.sh`
