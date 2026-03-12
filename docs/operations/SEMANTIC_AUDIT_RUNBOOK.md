# Semantic Audit Runbook

## Purpose

Audit cross-service contract semantics drift using:

- `contracts/registry.yaml`
- `contracts/semantic_policies/field_semantics.yaml`

## Commands

1. Sync contract indexes:

```bash
bash tools/local/sync_contract_indexes.sh
```

2. Run semantic audit (non-strict):

```bash
bash tools/local/audit_semantics.sh
```

3. Run strict mode (warnings fail):

```bash
bash tools/local/audit_semantics.sh --strict
```

4. Check warning budget by field:

```bash
bash tools/local/check_semantic_warning_budget.sh
```

## Output

- report: `verification/reports/semantic_audit.latest.json`
- aggregated summary field sink: `verification/reports/summary.latest.json` via `bash tools/local/aggregate_and_check.sh`
- exit code:
  - `0`: no error (warnings allowed in non-strict)
  - `1`: semantic hard errors (missing source/disallowed location)
  - `2`: strict mode warning failure

## Current policy boundary

Hard-fail checks:
- schema source must exist
- `allowed_locations` must not drift

Warning checks:
- `expected_shape` mismatch
- same field name appears with multiple shapes

Budget checks:
- `verification/reports/semantic_warning_budget.yaml`

## Agent Readyz gate matrix

用于统一 quick/regression/nightly 的 readyz 观测与阻断策略，避免环境间门禁语义漂移。

| Pipeline | 默认开关 | 默认 level | 默认 require report | 目标 |
| --- | --- | --- | --- | --- |
| quick | `WITH_AGENT_READYZ=0` | `red` | `0` | 本地/CI 快速反馈，默认不增加时延与阻断面 |
| regression | `--with-agent-readyz` | `red` | `1` | 回归链路要求 readyz 可采集，但对 level 先宽松 |
| nightly | `--with-agent-readyz` | `yellow` | `1` | 夜间链路阻断更严格，提前暴露降级风险 |

推荐启用方式：

```bash
# quick（可选观测，默认关闭）
WITH_AGENT_READYZ=1 MAX_AGENT_READYZ_LEVEL=red \
bash tools/ci/verify_quick.sh

# regression（默认已启用）
bash tools/ci/verify_regression.sh

# nightly（默认已启用，且默认 yellow）
bash tools/ci/verify_nightly.sh
```

readyz 失败排障顺序：
1. 先单独生成 readyz 报告：`bash tools/local/run_agent_readyz_report.sh`
2. 查看 `agent_readyz.latest.json` 的 `status_level/errors/checks`
3. 再复跑聚合：`bash tools/local/aggregate_and_check.sh --with-agent-readyz --skip-thresholds`
4. 最后执行带阈值门禁的 CI 入口（quick/regression/nightly）
