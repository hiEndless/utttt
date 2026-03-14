# Release Gate Checklist Template

更新时间：2026-03-13

用于统一 `RELEASE_LATEST` / `RELEASE_SUMMARY_*` / `RELEASE_HANDOFF_*` 的门禁记录口径。

## 1. 门禁默认矩阵

| Pipeline | readyz 开关 | MAX_AGENT_READYZ_LEVEL | REQUIRE_AGENT_READYZ_REPORT |
| --- | --- | --- | --- |
| quick | `WITH_AGENT_READYZ=0`（可选开启） | `red` + `MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=-1` | `0` |
| regression | 默认开启 `--with-agent-readyz` | `red` + `MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=-1` | `1` |
| nightly | 默认开启 `--with-agent-readyz` | `yellow` + `MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=0` | `1` |

## 2. 发布记录项（模板）

1. 记录当次 CI 生效阈值：
   - `MAX_AGENT_READYZ_LEVEL`
   - `MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS`
   - `REQUIRE_AGENT_READYZ_REPORT`
2. 记录聚合报告实际值（`verification/reports/summary.latest.json`）：
  - `agent_readyz_status_level`
  - `agent_readyz_report_count`
  - `agent_readyz_error_count`
  - `agent_readyz_errors`
  - `decision_trace_schema_guard_invalid_records`
3. 记录发布门禁摘要（`bash tools/local/check_release_ready.sh --print-summary-only --summary-format json`）：
   - `env_overrides`
4. 放行条件（建议）：
  - `agent_readyz_report_count > 0`（当 `REQUIRE_AGENT_READYZ_REPORT=1`）
  - `agent_readyz_status_level <= MAX_AGENT_READYZ_LEVEL`
  - `decision_trace_schema_guard_invalid_records <= MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS`（当阈值 >= 0）

## 3. 标准排障顺序

1. `bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
2. `bash tools/local/run_agent_readyz_report.sh`
3. `bash tools/local/aggregate_and_check.sh --with-agent-readyz --skip-thresholds`
4. 复跑对应 CI 入口（quick/regression/nightly）

## 4. 常见触发最小复现（release gate schema）

场景：修改 `verification/reports/release_gate_summary_v1.schema.json` 后，`contract bundle` 提示需要补齐四件套。

最小复现命令：

```bash
git checkout -b tmp/release-gate-schema-repro
echo "// repro" >> verification/reports/release_gate_summary_v1.schema.json
bash tools/local/check_contract_change_bundle_guard.sh
```

预期：守卫提示 schema 变更已触发，需要同步四件套。

修复步骤（最小）：
1. 补 `docs/CONTRACT_INDEX.md`（索引入口）
2. 补相关契约文档（`verification/reports/README.md`、`docs/contracts/CONTRACTS_QUICK_REF.md`）
3. 补运行说明（本模板或相关 release/runbook 文档）
4. 补守卫或测试（如 `verification/text/test_release_gate_summary_schema.py`）
