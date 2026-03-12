# Verification Script Inventory

更新时间：2026-03-12

## 1. 目的

给出当前 `scripts/` 下验证类脚本的分类清单，标记“已收编到 verification 层”与“待收编/保留”。

## 2. 已收编（通过 verification wrappers）

| legacy script | verification wrapper | status |
|---|---|---|
| `scripts/check_new_arch_guards.sh` | `verification/guards/new_arch_full.sh` | mapped |
| `scripts/check_new_arch_guards.sh --event-center-quick` | `verification/guards/new_arch_event_center_quick.sh` | mapped |
| `scripts/check_contract_docs_index_guard.sh` + `scripts/check_contract_docs_index_help_snapshot_guard.sh` | `verification/guards/contract_docs_index.sh` | mapped |
| `scripts/check_state_to_agent_contract_guard.sh` | `verification/guards/state_to_agent.sh` | mapped |
| `scripts/check_agent_to_execution_guard.sh` | `verification/guards/agent_to_execution.sh` | mapped |
| `scripts/check_event_center_replay_guard.sh` + `scripts/check_event_center_replay_summary_schema_guard.sh` | `verification/guards/event_center_replay.sh` | mapped |

说明：上述 wrapper 当前已优先直连 `tools/` 实现层（`tools/local` 或 `tools/ci`），
`scripts/*` 仅保留兼容入口与快照/文本扫描约束承载。

补充：以下 legacy 脚本实现已迁入 `tools/local`，`scripts/*` 仅保留兼容转发壳：

- `scripts/check_state_to_agent_contract_guard.sh` -> `tools/local/check_state_to_agent_contract_guard.sh`
- `scripts/check_agent_to_execution_guard.sh` -> `tools/local/check_agent_to_execution_guard.sh`
- `scripts/check_event_center_replay_guard.sh` -> `tools/local/check_event_center_replay_guard.sh`
- `scripts/check_contract_docs_index_guard.sh` -> `tools/local/check_contract_docs_index_guard.sh`

补充：`scripts/check_new_arch_guards.sh` 的全量执行主体已迁入
`tools/ci/new_arch_guards_full.sh`；保留 `scripts/check_new_arch_guards.sh`
中的参数解析与 event_center 分支以兼容现有“文本扫描型守卫”。

## 3. 保留为底层脚本（暂不迁移）

这些脚本当前作为“稳定底层执行单元”保留在 `scripts/`，由 verification wrapper 调用：

- `check_feature_contract_guard.sh`
- `check_feature_service_schema_guard.sh`
- `check_market_state_engine_guard.sh`
- `check_market_state_engine_help_snapshot_guard.sh`
- `check_runner_output_schema_guard.sh`
- `check_execution_*_schema_guard.sh`
- `check_execution_schema_mapping_guard.sh`
- `check_execution_breaking_version_bump_guard.sh`
- `check_execution_contract_entry_guard.sh`
- `check_alert_codes_entry_guard.sh`
- `check_event_center_contract_guards.sh`
- `check_event_center_contract_schema_guards.sh`
- `check_event_center_runtime_*`
- `check_event_center_ci_*`

## 4. 非验证类脚本

- `integration_smoke_new_arch.sh`（联调冒烟）
- `bump_event_center_runtime_version.sh`（版本号维护工具）

## 5. 下一阶段动作

1. 为 execution / feature / state / event_center 增加细粒度 wrapper（按领域分组）。
2. 逐步将 CI 调用从 `scripts/check_*` 切到 `verification/run_suite.sh`。
3. 保留 `scripts/check_*` 至少 1 个迭代周期后再评估精简。
