# Release Gate Checklist Template

更新时间：2026-03-13

用于统一 `RELEASE_LATEST` / `RELEASE_SUMMARY_*` / `RELEASE_HANDOFF_*` 的门禁记录口径。

## 1. 门禁默认矩阵

| Pipeline | readyz 开关 | MAX_AGENT_READYZ_LEVEL | REQUIRE_AGENT_READYZ_REPORT | legacy confidence |
| --- | --- | --- | --- | --- |
| quick | `WITH_AGENT_READYZ=0`（可选开启） | `red` | `0` | 不作为 quick 默认阻断 |
| regression | 默认开启 `--with-agent-readyz` | `red` | `1` | 不作为 regression 默认阻断 |
| nightly | 默认开启 `--with-agent-readyz` | `yellow` | `1` | `MAX_LEGACY_CONFIDENCE_RATIO=0.05`（可覆盖） |

## 2. 发布记录项（模板）

1. 记录当次 CI 生效阈值：
   - `MAX_LEGACY_CONFIDENCE_RATIO`
   - `MAX_AGENT_READYZ_LEVEL`
   - `REQUIRE_AGENT_READYZ_REPORT`
2. 记录聚合报告实际值（`verification/reports/summary.latest.json`）：
   - `execution_legacy_confidence_usage_ratio`
   - `agent_readyz_status_level`
   - `agent_readyz_report_count`
   - `agent_readyz_error_count`
   - `agent_readyz_errors`
3. 放行条件（建议）：
   - `execution_legacy_confidence_usage_ratio <= MAX_LEGACY_CONFIDENCE_RATIO`（nightly）
   - `agent_readyz_report_count > 0`（当 `REQUIRE_AGENT_READYZ_REPORT=1`）
   - `agent_readyz_status_level <= MAX_AGENT_READYZ_LEVEL`

## 3. 标准排障顺序

1. `bash tools/local/check_contract_change_bundle_guard.sh --show-detected-versions`
2. `bash tools/local/run_agent_readyz_report.sh`
3. `bash tools/local/aggregate_and_check.sh --with-agent-readyz --skip-thresholds`
4. 复跑对应 CI 入口（quick/regression/nightly）
