# Verification Compatibility Window

更新时间：2026-03-12
状态：completed

## 1. 目的

在 `verification` 新入口稳定期间，曾保留旧 `scripts/check_*` 入口一个迭代周期，避免 CI 和本地流程被破坏性切换。

## 2. 兼容窗口

- 开始：2026-03-12
- 最短保留周期：1 个迭代周期
- 实际结束条件（已满足）：
  1. CI 全量切换到 `tools/ci/verify_all.sh` 或 `verification/run_suite.sh`
  2. 本地使用文档已全部切换到 `tools/local/*`
  3. 最近 7 天无旧入口依赖阻塞记录

## 3. 当前兼容入口

- 当前兼容入口以机器清单为准：`verification/guards/script_compat_whitelist.yaml`
- 人工查看命令：
  1. `bash tools/local/check_script_compat_whitelist.sh`
  2. `./venv/bin/python -c "import yaml;d=yaml.safe_load(open('verification/guards/script_compat_whitelist.yaml'));print('hard=',len({i['path'] for k in ['hard_pinned_by_workflows','hard_pinned_by_snapshot_or_help_guards','hard_pinned_by_text_wiring_guards'] for i in d[k]}),'wrappers=',len(d['compatibility_wrappers_retained']))"`

对应新入口：`verification/guards/*.sh` 与 `tools/local/*.sh`（见 `verification/migration_map.yaml`）。
当前状态：兼容入口已清零（hard=0, wrappers=0）。

## 4. 下线前检查单

1. `tools/ci/verify_all.sh --quick` 在 CI 连续 7 天稳定。
2. `verification/run_suite.sh --suite=new_arch_full` 在主分支连续通过。
3. 关键文档入口已改为新路径：
   - `docs/ARCHITECTURE_NEW.md`
   - `docs/CONTRACTS_QUICK_REF.md`
4. 若下线旧入口，需在 PR 中附回滚方案（恢复旧脚本调用）。

## 5. 回滚策略

如新入口异常，回滚应基于 `tools/*` 入口进行，不再恢复 `scripts/*` 路径。
