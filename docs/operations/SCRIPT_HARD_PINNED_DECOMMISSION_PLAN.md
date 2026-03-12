# Script Hard-Pinned Decommission Plan

更新时间：2026-03-12

## 1. 目标

将仍被 hard-pinned 的 `scripts/*` 入口逐步解耦到 `tools/*`，并在兼容窗口结束后下线 wrapper。

## 2. 当前 hard-pinned 对象

以 `verification/guards/script_compat_whitelist.yaml` 为唯一准入源，当前唯一路径共 2 个：

1. `scripts/check_new_arch_guards.sh`
2. `scripts/check_event_center_contract_guards.sh`

## 3. 分批治理

### Batch A: Workflow pinning

状态：已完成（2026-03-12）

1. `.github/workflows/*` 已从 `scripts/ci_event_center_*.sh` 切换为 `tools/ci/*`。
2. workflow 守卫已改为校验 `tools/ci/*` 入口。
3. 相关 `scripts/ci_event_center_*.sh` 已转为 compatibility wrappers。

### Batch B: Snapshot/help pinning

状态：进行中（2026-03-12）

1. 已完成：`contract_docs_index` 与 `market_state_engine` 帮助快照守卫目标切换到 `tools/local/*`。
2. 待完成：`event_center` 帮助快照守卫目标切换到 `tools/*` 并刷新快照。
3. 验收：快照守卫连续通过后，下线对应历史 `scripts/*` 快照依赖。

### Batch C: Text wiring pinning

1. 将 `check_event_center_guard_wiring` 从脚本文本扫描迁移为“命令意图”检查。
2. 输入改为 `tools/ci/new_arch_guards_full.sh` + `tools/local/*`。
3. 验收：无脚本路径文本耦合后，允许删除旧 wiring 依赖。

## 4. 下线门禁

1. `bash tools/local/check_script_compat_whitelist.sh` 持续通过。  
2. `bash tools/ci/new_arch_guards_full.sh` 持续通过。  
3. `bash tools/ci/verify_quick.sh` 持续通过。  
4. 连续 1 个迭代周期无 `scripts/*` 依赖回退记录。
