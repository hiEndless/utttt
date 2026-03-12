# Script Hard-Pinned Decommission Plan

更新时间：2026-03-12

## 1. 目标

将仍被 hard-pinned 的 `scripts/*` 入口逐步解耦到 `tools/*`，并在兼容窗口结束后下线 wrapper。

## 2. 当前 hard-pinned 对象

以 `verification/guards/script_compat_whitelist.yaml` 为唯一准入源，当前唯一路径共 8 个：

1. `scripts/check_new_arch_guards.sh`
2. `scripts/check_event_center_contract_guards.sh`
3. `scripts/check_market_state_engine_guard.sh`
4. `scripts/ci_event_center_quick_strict.sh`
5. `scripts/ci_event_center_quick_lenient.sh`
6. `scripts/ci_event_center_full_strict.sh`
7. `scripts/ci_event_center_emit_meta_header.sh`
8. `scripts/check_contract_docs_index_guard.sh`

## 3. 分批治理

### Batch A: Workflow pinning

1. 将 `.github/workflows/*` 对 `scripts/ci_event_center_*.sh` 的调用切换为 `tools/ci/*`。
2. 将 workflow 守卫规则改为校验 `tools/ci/*` 入口。
3. 验收：CI 连续 7 天通过后，将对应 `scripts/ci_event_center_*.sh` 改为 wrapper 或下线。

### Batch B: Snapshot/help pinning

1. 将 help 快照守卫的目标入口改为 `tools/local/*`。
2. 刷新快照文件并在 PR 中附快照 diff。
3. 验收：快照守卫连续通过后，下线 `scripts/check_*_guard.sh` 的历史快照依赖。

### Batch C: Text wiring pinning

1. 将 `check_event_center_guard_wiring` 从脚本文本扫描迁移为“命令意图”检查。
2. 输入改为 `tools/ci/new_arch_guards_full.sh` + `tools/local/*`。
3. 验收：无脚本路径文本耦合后，允许删除旧 wiring 依赖。

## 4. 下线门禁

1. `bash tools/local/check_script_compat_whitelist.sh` 持续通过。  
2. `bash tools/ci/new_arch_guards_full.sh` 持续通过。  
3. `bash tools/ci/verify_quick.sh` 持续通过。  
4. 连续 1 个迭代周期无 `scripts/*` 依赖回退记录。
