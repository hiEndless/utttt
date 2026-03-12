# CLI Help Snapshot

更新时间：2026-03-13

用于冻结本地关键脚本的 `--help` 输出，降低参数语义漂移风险。

入口关系说明：
- `tools/local/verify_quick.sh` 是 `tools/ci/verify_quick.sh` 的本地代理入口。
- `tools/local/verify_full.sh` 是 `tools/ci/new_arch_guards_full.sh` 的本地代理入口。

## 刷新命令

```bash
bash tools/local/run_agent_memory_summary_report.sh --help
bash tools/local/verify_report_aggregate.sh --help
bash tools/local/aggregate_and_check.sh --help
bash tools/local/verify_quick.sh --help
bash tools/local/verify_full.sh --help
bash tools/local/check_semantic_critical_warning_guard.sh --help
bash tools/local/check_cli_help_snapshot_guard.sh
```

## `tools/local/run_agent_memory_summary_report.sh --help`

```text
Usage:
  bash tools/local/run_agent_memory_summary_report.sh [output_path] [runner_args...]
  bash tools/local/run_agent_memory_summary_report.sh --output <path> [runner_args...]

Options:
  --output <path>      memory summary 报告输出路径（默认 verification/reports/memory_summary.latest.json）
  --help, -h           显示帮助

Examples:
  bash tools/local/run_agent_memory_summary_report.sh
  bash tools/local/run_agent_memory_summary_report.sh /tmp/memory_summary.json --top-risk-n 10
  bash tools/local/run_agent_memory_summary_report.sh --output verification/reports/memory_summary.latest.json --risk-warning-min 2
```

## `tools/local/verify_report_aggregate.sh --help`

```text
Usage:
  bash tools/local/verify_report_aggregate.sh [options]

Options:
  --glob <pattern>             聚合输入 glob（默认 verification/reports/*.json）
  --output <path>              聚合输出路径（默认 verification/reports/summary.latest.json）
  --compact                    生成紧凑 JSON
  --with-memory-summary        聚合前先生成 memory summary 报告
  --memory-summary-path <path> memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --help, -h                   显示帮助
```

## `tools/local/aggregate_and_check.sh --help`

```text
Usage:
  bash tools/local/aggregate_and_check.sh [options]

Options:
  --with-memory-summary         先生成 memory summary 再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --compact                     生成紧凑 JSON（透传给 aggregate_reports --compact）
  --skip-thresholds             仅聚合，不执行阈值检查
  --max-legacy-confidence-ratio <float>
                               execution legacy confidence 占比上限（默认 -1 忽略）
  --help, -h                    显示帮助
```

## `tools/local/verify_full.sh --help`

```text
Usage:
  bash tools/local/verify_full.sh [args...]

Description:
  本地 full 验证入口，代理到：
    bash tools/ci/new_arch_guards_full.sh [args...]

Examples:
  bash tools/local/verify_full.sh
  bash tools/local/verify_full.sh --event-center-only
```

## `tools/local/verify_quick.sh --help`

```text
Usage:
  bash tools/local/verify_quick.sh [options] [args...]

Description:
  本地 quick 验证入口，代理到：
    bash tools/ci/verify_quick.sh [args...]

Options:
  --with-verification-api-schema-check   追加执行 verification API summary schema 开关校验测试
  --skip-semantic-critical-warning-guard 跳过 semantic critical warning guard（仅本地调试）
```

## `tools/local/check_semantic_critical_warning_guard.sh --help`

```text
Usage:
  bash tools/local/check_semantic_critical_warning_guard.sh [audit_report_json] [budget_yaml]

Description:
  读取 semantic audit 报告中的 warnings，按 budget 中 critical_fields 做阻断检查。

Args:
  audit_report_json  semantic audit 报告路径（默认 verification/reports/semantic_audit.latest.json）
  budget_yaml        关键字段预算文件（默认 verification/reports/semantic_critical_fields.yaml）

Failure Codes:
  exit 1  命中 critical field warning（阻断）
  exit 2  输入文件缺失或不可读
  exit 3  报告/预算解析失败
```
