# CLI Help Snapshot

更新时间：2026-03-13

用于冻结本地关键脚本的 `--help` 输出，降低参数语义漂移风险。

入口关系说明：
- `tools/local/verify_quick.sh` 是 `tools/ci/verify_quick.sh` 的本地代理入口。
- `tools/local/verify_full.sh` 是 `tools/ci/new_arch_guards_full.sh` 的本地代理入口。

文档守卫契约版本：
- `README_CONTRACTS_VERSION=readme-contracts-v2`

## 刷新命令

```bash
bash tools/local/run_agent_memory_summary_report.sh --help
bash tools/local/verify_report_aggregate.sh --help
bash tools/local/aggregate_and_check.sh --help
bash tools/local/verify_quick.sh --help
bash tools/local/verify_full.sh --help
bash tools/local/check_semantic_critical_warning_guard.sh --help
bash tools/ci/verify_quick.sh --help
bash tools/ci/verify_regression.sh --help
bash tools/ci/verify_nightly.sh --help
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
  --with-agent-readyz          聚合前先生成 agent readyz 报告
  --agent-readyz-path <path>   agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --with-decision-trace-schema-guard  聚合前先生成 decision_trace schema guard 报告
  --decision-trace-schema-guard-path <path> decision_trace schema guard 输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --with-pipeline-mode-report  聚合前先生成 pipeline_mode 灰度报告
  --pipeline-mode-report-path <path> pipeline_mode 报告输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --agent-readyz-base-url <url>  agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --help, -h                   显示帮助
```

## `tools/local/aggregate_and_check.sh --help`

```text
Usage:
  bash tools/local/aggregate_and_check.sh [options]

Options:
  --with-memory-summary         先生成 memory summary 再聚合
  --with-agent-readyz           先生成 agent readyz 报告再聚合
  --with-decision-trace-schema-guard  先生成 decision_trace schema guard 报告再聚合
  --with-pipeline-mode-report   先生成 pipeline_mode 灰度报告再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --agent-readyz-path <path>    agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --decision-trace-schema-guard-path <path>
                               decision_trace schema guard 报告输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --pipeline-mode-report-path <path>
                               pipeline_mode 报告输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --agent-readyz-base-url <url> agent readyz 基础地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec> agent readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
  --compact                     生成紧凑 JSON（透传给 aggregate_reports --compact）
  --skip-thresholds             仅聚合，不执行阈值检查
  --max-legacy-confidence-ratio <float>
                               execution legacy confidence 占比上限（默认 -1 忽略）
  --max-agent-readyz-level <green|yellow|red>
                               agent readyz 最大允许状态级别（默认 red）
  --max-decision-trace-schema-guard-invalid-records <int>
                               decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  --max-pipeline-mode-unknown-count <int>
                               pipeline_mode unknown 计数上限（默认 -1 忽略）
  --max-pipeline-mode-missing-count <int>
                               pipeline_mode 缺失计数上限（默认 -1 忽略）
  --require-agent-readyz-report 要求存在 agent readyz 报告（默认关闭）
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
  说明：继承 CI quick 全量门禁，包含 pipeline semantic terms doc guard。

Options:
  --with-verification-api-schema-check   追加执行 verification API summary schema 开关校验测试
  --skip-semantic-critical-warning-guard 跳过 semantic critical warning guard（仅本地调试）
  --skip-release-baseline-alignment      跳过 release baseline 对齐校验（仅本地调试）
  --with-agent-readyz                    启用 agent readyz 聚合观测（默认关闭）
  --with-pipeline-mode-report            启用 pipeline_mode 灰度聚合观测（默认关闭）
  --max-agent-readyz-level <level>       设置 readyz 最大允许级别（默认 red）
  --require-agent-readyz-report          要求存在 readyz 报告（默认关闭）
  --agent-readyz-base-url <url>          指定 readyz 地址（默认 AGENT_BASE_URL 或 http://127.0.0.1:9971）
  --agent-readyz-timeout-s <sec>         指定 readyz 拉取超时秒数（默认 AGENT_READYZ_TIMEOUT_S 或 2.0）
```

约束说明：
- 上述 `--skip-*` 仅允许本地调试使用。
- CI 环境（`CI=true` 或 `GITHUB_ACTIONS=true`）若设置
  `VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1` 或 `VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1`
  将直接失败（`tools/ci/verify_quick.sh` 退出码 `2`）。

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

## `tools/ci/verify_quick.sh --help`

```text
Usage:
  bash tools/ci/verify_quick.sh

Description:
  CI quick 验证入口。执行结构守卫、docs/contracts 聚合守卫（含 pipeline semantic terms doc guard）、链路 quick suite 与语义审计后处理。

Environment Switches (local debug only):
  VERIFY_QUICK_SKIP_RELEASE_BASELINE_ALIGNMENT=1
  VERIFY_QUICK_SKIP_SEMANTIC_CRITICAL=1

Optional Observability:
  WITH_AGENT_READYZ=1            启用 agent readyz 聚合观测（默认关闭）
  WITH_PIPELINE_MODE_REPORT=1    启用 pipeline_mode 灰度聚合观测（默认关闭）
  MAX_AGENT_READYZ_LEVEL         readyz 最大允许级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS
                                decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT
                                pipeline_mode unknown 计数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_MISSING_COUNT
                                pipeline_mode 缺失计数上限（默认 -1 忽略）
  REQUIRE_AGENT_READYZ_REPORT    是否要求 readyz 报告存在（1/0，默认 0）
  AGENT_READYZ_BASE_URL          agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S         agent readyz 拉取超时秒数（默认 2.0）

CI Hard Constraints:
  当 CI=true 或 GITHUB_ACTIONS=true 时，禁止启用上述 skip 开关；若启用会直接失败（exit 2）。

Failure Codes:
  exit 1  任一守卫/测试失败
  exit 2  CI 环境下启用了禁止的 skip 开关
```

## `tools/ci/verify_regression.sh --help`

```text
Usage:
  bash tools/ci/verify_regression.sh

Description:
  CI regression 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、event-center quick 回归链路与语义审计。

Environment:
  MAX_AGENT_READYZ_LEVEL        agent readyz 最大允许级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS  decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT  pipeline_mode unknown 计数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_MISSING_COUNT  pipeline_mode 缺失计数上限（默认 -1 忽略）
  REQUIRE_AGENT_READYZ_REPORT   是否要求 readyz 报告存在（1/0，默认 1）
  AGENT_READYZ_BASE_URL         agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S        agent readyz 拉取超时秒数（默认 2.0）

Failure Codes:
  exit 1  任一守卫/测试失败
```

## `tools/ci/verify_nightly.sh --help`

```text
Usage:
  bash tools/ci/verify_nightly.sh

Description:
  CI nightly 验证入口。执行结构与文档快照守卫、pipeline semantic terms doc guard、全量报告回归链路与语义聚合校验。

Environment:
  MAX_LEGACY_CONFIDENCE_RATIO   execution legacy confidence 占比上限（默认 0.05）
  MAX_AGENT_READYZ_LEVEL        agent readyz 最大允许级别（默认 yellow）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS  decision_trace schema guard invalid 记录数上限（默认 0）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT  pipeline_mode unknown 计数上限（默认 0）
  MAX_PIPELINE_MODE_MISSING_COUNT  pipeline_mode 缺失计数上限（默认 0）
  REQUIRE_AGENT_READYZ_REPORT   是否要求 readyz 报告存在（1/0，默认 1）
  AGENT_READYZ_BASE_URL         agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S        agent readyz 拉取超时秒数（默认 2.0）

Failure Codes:
  exit 1  任一守卫/测试失败
```
