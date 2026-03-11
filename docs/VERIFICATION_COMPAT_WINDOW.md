# Verification Compatibility Window

更新时间：2026-03-12
状态：active

## 1. 目的

在 `verification` 新入口稳定期间，保留旧 `scripts/check_*` 入口一个迭代周期，避免 CI 和本地流程被破坏性切换。

## 2. 兼容窗口

- 开始：2026-03-12
- 最短保留周期：1 个迭代周期
- 结束前提：
  1. CI 全量切换到 `tools/ci/verify_all.sh` 或 `verification/run_suite.sh`
  2. 本地使用文档已全部切换到 `tools/local/*`
  3. 最近 7 天无旧入口依赖阻塞记录

## 3. 当前兼容入口

- `scripts/check_new_arch_guards.sh`
- `scripts/check_state_to_agent_contract_guard.sh`
- `scripts/check_agent_to_execution_guard.sh`
- `scripts/check_contract_docs_index_guard.sh`
- `scripts/check_contract_docs_index_help_snapshot_guard.sh`
- `scripts/check_event_center_replay_guard.sh`
- `scripts/check_event_center_replay_summary_schema_guard.sh`

对应新入口：`verification/guards/*.sh`（见 `verification/migration_map.yaml`）。

## 4. 下线前检查单

1. `tools/ci/verify_all.sh --quick` 在 CI 连续 7 天稳定。
2. `verification/run_suite.sh --suite=new_arch_full` 在主分支连续通过。
3. 关键文档入口已改为新路径：
   - `docs/ARCHITECTURE_NEW.md`
   - `docs/CONTRACTS_QUICK_REF.md`
4. 若下线旧入口，需在 PR 中附回滚方案（恢复旧脚本调用）。

## 5. 回滚策略

如新入口异常，可临时恢复 CI 调用旧 `scripts/check_*`，并保留失败日志与失败码记录。
