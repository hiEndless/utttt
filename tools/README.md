# Tools

Unified operational entrypoints.

CI:
- `tools/ci/verify_all.sh`
- `tools/ci/verify_quick.sh`
- `tools/ci/verify_regression.sh`
- `tools/ci/verify_nightly.sh`
- `tools/ci/new_arch_guards_full.sh`
- `tools/ci/event_center_quick_strict.sh`
- `tools/ci/event_center_quick_lenient.sh`
- `tools/ci/event_center_full_strict.sh`
- `tools/ci/event_center_emit_meta_header.sh`
- `tools/ci/event_center_emit_guard_summary.sh`

Local:
- `tools/local/check_structure.sh`
- `tools/local/check_services_map_consistency.sh`
- `tools/local/sync_contract_schemas.sh`
- `tools/local/sync_contract_mappings.sh`
- `tools/local/sync_contract_indexes.sh`
- `tools/local/audit_semantics.sh`
- `tools/local/check_semantic_warning_budget.sh`
- `tools/local/check_script_compat_whitelist.sh`
- `tools/local/check_state_to_agent_contract_guard.sh`
- `tools/local/check_agent_to_execution_guard.sh`
- `tools/local/check_event_center_replay_guard.sh`
- `tools/local/check_contract_docs_index_guard.sh`
- `tools/local/verify_quick.sh`
- `tools/local/verify_full.sh`
- `tools/local/verify_quick_report.sh`
- `tools/local/replay_event_center.sh`
- `tools/local/verify_report_aggregate.sh`
- `tools/local/run_agent_memory_summary_report.sh`
- `tools/local/run_agent_readyz_report.sh`
- `tools/local/verify_thresholds.sh`
- `tools/local/run_verification_api.sh`
- `tools/local/diff_json.sh`
- `tools/local/aggregate_and_check.sh`
- `tools/local/run_feature_service.sh`
- `tools/local/run_market_state_engine.sh`
- `tools/local/run_event_center.sh`
- `tools/local/run_event_center_replay.sh`
- `tools/local/run_agent_runner.sh`
- `tools/local/run_agent_pipeline_smoke.sh`
- `tools/local/run_agent_memory_summary.sh`
- `tools/local/run_execution_service.sh`

Notes:
- `tools/local/verify_quick.sh` 是本地 quick 代理入口，实际执行 `tools/ci/verify_quick.sh`。
- `tools/local/verify_full.sh` 是本地 full 代理入口，实际执行 `tools/ci/new_arch_guards_full.sh`。
