# UTaker 契约索引

更新时间：2026-03-12
说明：部分核心入口受守卫脚本强约束（`tools/local/check_contract_docs_index_guard.sh`），请勿随意移除或改名。

## 1. 架构与总入口

- `docs/ARCHITECTURE_NEW.md`
- `docs/CONTRACTS_QUICK_REF.md`
- `docs/contract_docs_index_help_snapshot.txt`
- `docs/new_arch_guards_help_snapshot.txt`
- `docs/operations/NEW_ARCH_GUARDS_HELP_SNAPSHOT_RUNBOOK.md`
- `docs/operations/VERIFICATION_SCRIPT_INVENTORY.md`
- `docs/operations/VERIFY_QUICK_DEDUP_MATRIX.md`
- `docs/operations/VERIFY_QUICK_TIMING_BASELINE.md`
- `docs/REFACTOR_PLAYBOOK_NEW.md`
- `docs/DECISION_CONFIDENCE_MIGRATION.md`
- `docs/SEMANTIC_GLOSSARY.md`
- `docs/ALERT_CODES.md`
- `tools/local/check_contract_docs_canonical_layout_guard.sh`
- `tools/local/check_contract_change_bundle_guard.sh`（强约束触发：schema 文件变更、schema_mapping 变更，或 event_center_runtime_config_version 版本锚点变更）

## 2. feature_service

- `feature_contract_version: feature-contract-v1`
- `feature_response_schema_version: 1.0`
- `services/feature_service/docs/api.md`
- `services/feature_service/docs/boundaries.md`
- `tools/local/check_feature_contract_guard.sh`
- `tools/local/check_feature_contract_entry_guard.sh`

## 3. market_state_engine

- `market_state_contract_version: market-state-contract-v1`
- `market_state_msl_schema_version: 2`
- `services/market_state_engine/docs/api.md`
- `services/market_state_engine/docs/boundaries.md`
- `services/market_state_engine/docs/guard_help_snapshot.txt`
- `services/market_state_engine/docs/msl.schema.json`
- `tools/local/check_market_state_contract_entry_guard.sh`

## 4. event_center_new

- `event_center_runtime_config_version: event-center-runtime-v1`
- `services/event_center_new/docs/schema.md`
- `services/event_center_new/docs/refactor.md`
- `services/event_center_new/docs/runtime.md`
- `services/event_center_new/docs/ci_baseline_template.md`
- `services/event_center_new/docs/selected_event.schema.json`
- `services/event_center_new/docs/replay_summary.schema.json`
- `tools/local/check_event_center_contract_entry_guard.sh`

## 5. agent_server_new

- `services/agent_server_new/docs/REFACTOR_PLAN_V2.md`
- `services/agent_server_new/docs/runner_output_contract.md`
- `services/agent_server_new/docs/runner_output.schema.json`
- `tools/local/check_state_to_agent_contract_guard.sh`（含 active_events 最小契约与 traceability 守卫）
- `tools/local/check_cross_service_time_semantics_doc_guard.sh`（跨 event/state/agent/execution 的时间语义文档一致性守卫）

## 6. execution_service

- `execution_schema_mapping_version: execution-schema-mapping-v16`
- `tools/local/check_execution_contract_entry_guard.sh`
- `services/execution_service/docs/api.md`
- `services/execution_service/docs/boundaries.md`
- `services/execution_service/docs/migration.md`
- `services/execution_service/docs/decision_intent.schema.json`
- `services/execution_service/docs/decision_confidence.schema.json`
- `services/execution_service/docs/execution_result.schema.json`
- `services/execution_service/docs/execution_action.schema.json`
- `services/execution_service/docs/execution_enums.schema.json`
- `services/execution_service/docs/reject_reason.schema.json`
- `services/execution_service/docs/execution_io_payload.schema.json`
- `services/execution_service/docs/policy_snapshot.schema.json`
- `services/execution_service/docs/execution_signal_result.schema.json`
- `services/execution_service/docs/decision_state.schema.json`
- `services/execution_service/docs/decision_state_status.schema.json`
- `services/execution_service/docs/risk_state.schema.json`
- `services/execution_service/docs/risk_state_change_reason.schema.json`
- `services/execution_service/docs/rule_debug.schema.json`
- `services/execution_service/docs/evaluation_trace.schema.json`
- `services/execution_service/docs/signal_action.schema.json`
- `services/execution_service/docs/signal_mode.schema.json`
- `services/execution_service/docs/risk_checks.schema.json`
- `services/execution_service/docs/rule_priority_order.schema.json`
- `services/execution_service/docs/position_mode.schema.json`
- `services/execution_service/docs/signal_scope.schema.json`
- `services/execution_service/docs/position_before.schema.json`
- `services/execution_service/docs/position_after_simulation.schema.json`
- `services/execution_service/docs/execution_reconcile_result.schema.json`
- `services/execution_service/docs/retry_meta.schema.json`
- `services/execution_service/docs/risk_policy.schema.json`
- `services/execution_service/docs/schema_mapping.json`
- `services/execution_service/docs/redis_keys.md`
- `services/execution_service/docs/curl_examples.md`
- `services/execution_service/docs/httpie_examples.md`

## 7. 深度流水线文档（防语义漂移）

- `docs/contracts/pipelines/agent_server_new_data_pipeline.md`
- `docs/contracts/pipelines/market_state_engine_data_pipeline.md`
- `docs/contracts/pipelines/event_center_new_data_contracts.md`
- `docs/contracts/pipelines/execution_service_data_pipeline.md`
