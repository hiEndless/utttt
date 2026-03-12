# Script Hard-Pinned Decommission Plan

更新时间：2026-03-12

## 1. 目标

将仍被 hard-pinned 的 `scripts/*` 入口逐步解耦到 `tools/*`，并在兼容窗口结束后下线 wrapper。

## 2. 当前 hard-pinned 对象

以 `verification/guards/script_compat_whitelist.yaml` 为唯一准入源，当前唯一路径共 0 个（已清零）。

## 3. 分批治理

### Batch A: Workflow pinning

状态：已完成（2026-03-12）

1. `.github/workflows/*` 已从 `scripts/ci_event_center_*.sh` 切换为 `tools/ci/*`。
2. workflow 守卫已改为校验 `tools/ci/*` 入口。
3. 相关 `scripts/ci_event_center_*.sh` 已下线（移除兼容 wrappers）。

### Batch B: Snapshot/help pinning

状态：已完成（2026-03-12）

1. 已完成：`contract_docs_index`、`market_state_engine`、`event_center` 帮助快照守卫目标切换到 `tools/*`。
2. 快照守卫已连续通过，相关 `scripts/*` 路径已下线。

### Batch C: Text wiring pinning

状态：已完成（2026-03-12）

1. `check_event_center_guard_wiring` 已切到扫描 `tools/local/*` 主入口。
2. `check_new_arch_guards` 已迁移到 `tools/local`，legacy wrapper 已下线。
3. hard-pinned 清单已清零，兼容 wrapper 已清零。

## 4. 下线门禁

1. `bash tools/local/check_script_compat_whitelist.sh` 持续通过。  
2. `bash tools/ci/new_arch_guards_full.sh` 持续通过。  
3. `bash tools/ci/verify_quick.sh` 持续通过。  
4. 连续 1 个迭代周期无 `scripts/*` 依赖回退记录。
