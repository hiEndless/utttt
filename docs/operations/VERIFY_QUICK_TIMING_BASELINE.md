# Verify Quick Timing Baseline

更新时间：2026-03-12
来源：`tools/local/profile_verify_quick_guards.sh`
JSON 报告：`verification/reports/verify_quick_timing.latest.json`

## 汇总

- 累计步骤耗时：`4775 ms`
- 墙钟耗时：`5043 ms`

## 逐步耗时

| Step | Status | Duration (ms) |
|---|---|---:|
| `check_structure` | `passed` | 137 |
| `check_script_compat_whitelist` | `passed` | 130 |
| `check_docs_contracts_bundle` | `passed` | 388 |
| `verify_all_quick` | `passed` | 3628 |
| `sync_contract_indexes` | `passed` | 232 |
| `audit_semantics` | `passed` | 137 |
| `check_semantic_critical_warning_guard` | `passed` | 123 |

## 说明

- 该基线用于观察 `verify_quick` 外层编排变化后的趋势。
- 如需刷新，执行：
```bash
bash tools/local/profile_verify_quick_guards.sh
```
