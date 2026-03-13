# CLI Help Snapshot

更新时间：2026-03-14

用于冻结本地关键脚本的 `--help` 输出，降低参数语义漂移风险。

入口关系说明：
- `tools/local/verify_quick.sh` 是 `tools/ci/verify_quick.sh` 的本地代理入口。
- `tools/local/verify_full.sh` 是 `tools/ci/new_arch_guards_full.sh` 的本地代理入口。

文档守卫契约版本：
- `README_CONTRACTS_VERSION=readme-contracts-v2`

README 契约版本升级提示：
1. 先更新 `verification/text/readme_contracts.py` 中的 `README_CONTRACTS_VERSION`
2. 再同步 `verification/text/readme_contracts_version.baseline`
3. 最后同步本文件中的版本锚点

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
  --with-execution-prompt-report  聚合前先生成 execution prompt 版本报告
  --execution-prompt-report-path <path> execution prompt 报告输出路径（默认 verification/reports/execution_prompt_version.latest.json）
  --with-event-type-match-report  聚合前先生成 event_type 命中报告
  --event-type-match-report-path <path> event_type 命中报告输出路径（默认 verification/reports/agent_event_type_match.latest.json）
  --with-agent-action-hint-semantics-report  聚合前先生成 action_hint 语义映射报告
  --agent-action-hint-semantics-report-path <path> action_hint 语义映射报告输出路径（默认 verification/reports/agent_action_hint_semantics.latest.json）
  --with-signal-decision-llm-observe-report  聚合前先生成 signal decision LLM observe 报告
  --signal-decision-llm-observe-report-path <path> signal decision LLM observe 报告输出路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
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
  --with-execution-prompt-report  先生成 execution prompt 版本报告再聚合
  --with-event-type-match-report  先生成 event_type 命中报告再聚合
  --with-agent-action-hint-semantics-report  先生成 action_hint 语义映射报告再聚合
  --with-signal-decision-llm-observe-report  先生成 signal decision LLM observe 报告再聚合
  --summary-path <path>         聚合报告输出路径（默认 verification/reports/summary.latest.json）
  --memory-summary-path <path>  memory summary 输出路径（默认 verification/reports/memory_summary.latest.json）
  --agent-readyz-path <path>    agent readyz 报告输出路径（默认 verification/reports/agent_readyz.latest.json）
  --decision-trace-schema-guard-path <path>
                               decision_trace schema guard 报告输出路径（默认 verification/reports/agent_decision_trace_schema_guard.latest.json）
  --pipeline-mode-report-path <path>
                               pipeline_mode 报告输出路径（默认 verification/reports/agent_pipeline_mode.latest.json）
  --execution-prompt-report-path <path>
                               execution prompt 报告输出路径（默认 verification/reports/execution_prompt_version.latest.json）
  --event-type-match-report-path <path>
                               event_type 命中报告输出路径（默认 verification/reports/agent_event_type_match.latest.json）
  --agent-action-hint-semantics-report-path <path>
                               action_hint 语义映射报告输出路径（默认 verification/reports/agent_action_hint_semantics.latest.json）
  --signal-decision-llm-observe-report-path <path>
                               signal decision LLM observe 报告输出路径（默认 verification/reports/agent_signal_decision_llm_observe.latest.json）
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
  --max-event-type-match-missing-count <int>
                               event_type_match 缺失计数上限（默认 -1 忽略）
  --max-event-type-match-unknown-count <int>
                               event_type_match unknown 计数上限（默认 -1 忽略）
  --min-event-type-match-alias-ratio <float>
                               event_type_match alias 占比下限（默认 -1 忽略）
  --max-decision-agent-key-unknown-count <int>
                               decision_agent_key unknown 计数上限（默认 -1 忽略）
  --max-route-replay-mismatch-count <int>
                               route_replay mismatch 计数上限（默认 -1 忽略）
  --max-action-hint-semantics-mismatch-count <int>
                               action_hint_semantics mismatch 计数上限（默认 -1 忽略）
  --max-action-hint-semantics-missing-actual-hint-count <int>
                               action_hint_semantics missing_actual_hint 计数上限（默认 -1 忽略）
  --min-action-hint-semantics-match-ratio <float>
                               action_hint_semantics match_ratio 下限（默认 -1 忽略）
  --max-signal-decision-llm-observe-missing-decision-mode-count <int>
                               signal_decision_llm_observe missing_decision_mode 计数上限（默认 -1 忽略）
  --max-signal-decision-llm-observe-missing-llm-parse-status-count <int>
                               signal_decision_llm_observe missing_llm_parse_status 计数上限（默认 -1 忽略）
  --min-signal-decision-llm-observe-decision-mode-llm-count <int>
                               signal_decision_llm_observe decision_mode_llm_count 下限（默认 -1 忽略）
  --min-signal-decision-llm-observe-llm-parse-status-llm-ok-count <int>
                               signal_decision_llm_observe llm_parse_status_llm_ok_count 下限（默认 -1 忽略）
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
  --with-agent-closed-loop-smoke         启用 agent->execution 三态闭环自检（默认关闭）
  --with-agent-action-hint-semantics-report
                                          启用 minimal 语义映射聚合观测（默认关闭）
  --with-agent-action-hint-cases-report   生成 action_hint mismatch 回放 artifact（默认关闭）
  --with-agent-decision-agent-key-report  启用 decision_agent_key 路由分布观测（默认关闭）
  --with-agent-route-replay-report        启用四类来源业务路由回放观测（默认关闭）
  --with-agent-signal-decision-replay-report
                                          启用信号决策结果回放观测（默认关闭）
  --agent-action-hint-cases-report-path <path>
                                          指定 action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  --agent-action-hint-missing-cases-report-path <path>
                                          指定 action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
  --agent-decision-agent-key-report-path <path>
                                          指定 decision_agent_key 报告输出路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  --agent-route-replay-report-path <path>
                                          指定 route replay 报告输出路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  --agent-signal-decision-replay-report-path <path>
                                          指定 signal decision replay 报告输出路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  --agent-signal-decision-replay-min-source-count <int>
                                          指定 signal decision replay 每来源最小样本数（默认 10）
  --max-market-indicator-rule-fallback-ratio <float>
                                          指定 market_indicator 的 rule_fallback 比例上限（默认 -1 忽略）
  --max-onchain-wallet-rule-fallback-ratio <float>
                                          指定 onchain_wallet 的 rule_fallback 比例上限（默认 -1 忽略）
  --max-large-liquidation-rule-fallback-ratio <float>
                                          指定 large_liquidation 的 rule_fallback 比例上限（默认 -1 忽略）
  --max-social-news-rule-fallback-ratio <float>
                                          指定 social_news 的 rule_fallback 比例上限（默认 -1 忽略）
  --max-agent-readyz-level <level>       设置 readyz 最大允许级别（默认 red）
  --max-decision-agent-key-unknown-count <int>
                                          设置 decision_agent_key unknown 计数上限（默认 -1 忽略）
  --max-route-replay-mismatch-count <int>
                                          设置 route_replay mismatch 计数上限（默认 -1 忽略）
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
  WITH_AGENT_CLOSED_LOOP_SMOKE=1 启用 agent->execution 三态闭环自检（默认关闭）
  WITH_AGENT_ACTION_HINT_SEMANTICS_REPORT=1
                                启用 minimal 语义映射聚合观测（默认关闭）
  WITH_AGENT_ACTION_HINT_CASES_REPORT=1
                                生成 action_hint mismatch 回放 artifact（默认关闭）
  WITH_AGENT_DECISION_AGENT_KEY_REPORT=1
                                启用 decision_agent_key 路由分布观测（默认关闭）
  WITH_AGENT_ROUTE_REPLAY_REPORT=1
                                启用四类来源业务路由回放观测（默认关闭）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT=1
                                启用信号决策结果回放观测（默认关闭）
  AGENT_ACTION_HINT_CASES_REPORT_PATH
                                action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH
                                action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
  AGENT_DECISION_AGENT_KEY_REPORT_PATH
                                decision_agent_key 报告输出路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  AGENT_ROUTE_REPLAY_REPORT_PATH
                                route replay 报告输出路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH
                                signal decision replay 报告输出路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT
                                signal decision replay 每来源最小样本数（默认 10）
  MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO
                                market_indicator 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO
                                onchain_wallet 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO
                                large_liquidation 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO
                                social_news 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_AGENT_READYZ_LEVEL         readyz 最大允许级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS
                                decision_trace schema guard invalid 记录数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_UNKNOWN_COUNT
                                pipeline_mode unknown 计数上限（默认 -1 忽略）
  MAX_PIPELINE_MODE_MISSING_COUNT
                                pipeline_mode 缺失计数上限（默认 -1 忽略）
  MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT
                                decision_agent_key unknown 计数上限（默认 -1 忽略）
  MAX_DECISION_AGENT_KEY_GENERIC_RATIO
                                decision_agent_key generic 占比上限（默认 -1 忽略）
  MAX_ROUTE_REPLAY_MISMATCH_COUNT
                                route_replay mismatch 计数上限（默认 -1 忽略）
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
  MAX_EVENT_TYPE_MATCH_MISSING_COUNT  event_type_match 缺失计数上限（默认 -1 忽略）
  MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT  event_type_match unknown 计数上限（默认 -1 忽略）
  MIN_EVENT_TYPE_MATCH_ALIAS_RATIO  event_type_match alias 占比下限（默认 0.01）
  WITH_AGENT_DECISION_AGENT_KEY_REPORT  是否生成 decision_agent_key 路由分布 artifact（1/0，默认 1）
  AGENT_DECISION_AGENT_KEY_REPORT_PATH  decision_agent_key 报告路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT  decision_agent_key unknown 计数上限（默认 -1 忽略）
  MAX_DECISION_AGENT_KEY_GENERIC_RATIO  decision_agent_key generic 占比上限（默认 -1 忽略）
  WITH_AGENT_ROUTE_REPLAY_REPORT  是否生成四类来源业务路由回放 artifact（1/0，默认 1）
  AGENT_ROUTE_REPLAY_REPORT_PATH  route replay 报告路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  MAX_ROUTE_REPLAY_MISMATCH_COUNT  route_replay mismatch 计数上限（默认 -1 忽略）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT  是否生成信号决策回放 artifact（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH  signal decision replay 报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT  signal decision replay 每来源最小样本数（默认 10）
  MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO  market_indicator 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO  onchain_wallet 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO  large_liquidation 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO  social_news 的 rule_fallback 比例上限（默认 0.85）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_HINT  是否输出 recommendation 发布候选提示（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH  recommendation 报告路径（默认 verification/reports/agent_signal_decision_replay_recommendation.latest.json）
  MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT  action_hint_semantics mismatch 计数上限（默认 1）
  MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT  action_hint_semantics missing_actual_hint 计数上限（默认 1）
  MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO  action_hint_semantics match_ratio 下限（默认 0.90）
  WITH_AGENT_ACTION_HINT_CASES_REPORT  是否生成 action_hint mismatch 回放 artifact（1/0，默认 1）
  AGENT_ACTION_HINT_CASES_REPORT_PATH  action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH  action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
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
  MAX_EVENT_TYPE_MATCH_MISSING_COUNT  event_type_match 缺失计数上限（默认 0）
  MAX_EVENT_TYPE_MATCH_UNKNOWN_COUNT  event_type_match unknown 计数上限（默认 0）
  MIN_EVENT_TYPE_MATCH_ALIAS_RATIO  event_type_match alias 占比下限（默认 -1 忽略）
  WITH_AGENT_DECISION_AGENT_KEY_REPORT  是否生成 decision_agent_key 路由分布 artifact（1/0，默认 1）
  AGENT_DECISION_AGENT_KEY_REPORT_PATH  decision_agent_key 报告路径（默认 verification/reports/agent_decision_agent_key.latest.json）
  MAX_DECISION_AGENT_KEY_UNKNOWN_COUNT  decision_agent_key unknown 计数上限（默认 0）
  MAX_DECISION_AGENT_KEY_GENERIC_RATIO  decision_agent_key generic 占比上限（默认 0.40）
  WITH_AGENT_ROUTE_REPLAY_REPORT  是否生成四类来源业务路由回放 artifact（1/0，默认 1）
  AGENT_ROUTE_REPLAY_REPORT_PATH  route replay 报告路径（默认 verification/reports/agent_signal_source_route_replay.latest.json）
  MAX_ROUTE_REPLAY_MISMATCH_COUNT  route_replay mismatch 计数上限（默认 0）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_REPORT  是否生成信号决策回放 artifact（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_REPORT_PATH  signal decision replay 报告路径（默认 verification/reports/agent_signal_decision_replay.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_MIN_SOURCE_COUNT  signal decision replay 每来源最小样本数（默认 10）
  MAX_MARKET_INDICATOR_RULE_FALLBACK_RATIO  market_indicator 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_ONCHAIN_WALLET_RULE_FALLBACK_RATIO  onchain_wallet 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_LARGE_LIQUIDATION_RULE_FALLBACK_RATIO  large_liquidation 的 rule_fallback 比例上限（默认 -1 忽略）
  MAX_SOCIAL_NEWS_RULE_FALLBACK_RATIO  social_news 的 rule_fallback 比例上限（默认 0.90）
  WITH_AGENT_SIGNAL_DECISION_REPLAY_TREND  是否输出 signal decision replay 趋势摘要（1/0，默认 1）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_GLOB  趋势输入 glob（默认 verification/reports/agent_signal_decision_replay*.json）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_DAYS  趋势窗口天数（默认 7）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_SOURCE  趋势来源类型（默认 social_news）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_REPORT_PATH  趋势报告输出路径（默认 verification/reports/agent_signal_decision_replay_trend.latest.json）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_RATIO  趋势建议触发阈值（默认 0.70）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_DAYS  趋势建议连续天数下限（默认 3）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMEND_MIN_TOTAL  趋势建议总样本数下限（默认 20）
  AGENT_SIGNAL_DECISION_REPLAY_TREND_RECOMMENDATION_REPORT_PATH  趋势建议输出路径（默认 verification/reports/agent_signal_decision_replay_recommendation.latest.json）
  MAX_ACTION_HINT_SEMANTICS_MISMATCH_COUNT  action_hint_semantics mismatch 计数上限（默认 0）
  MAX_ACTION_HINT_SEMANTICS_MISSING_ACTUAL_HINT_COUNT  action_hint_semantics missing_actual_hint 计数上限（默认 0）
  MIN_ACTION_HINT_SEMANTICS_MATCH_RATIO  action_hint_semantics match_ratio 下限（默认 0.95）
  MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_DECISION_MODE_COUNT  signal_decision_llm_observe missing_decision_mode 计数上限（默认 0）
  MAX_SIGNAL_DECISION_LLM_OBSERVE_MISSING_LLM_PARSE_STATUS_COUNT  signal_decision_llm_observe missing_llm_parse_status 计数上限（默认 0）
  MIN_SIGNAL_DECISION_LLM_OBSERVE_DECISION_MODE_LLM_COUNT  signal_decision_llm_observe decision_mode_llm_count 下限（默认 -1 忽略）
  MIN_SIGNAL_DECISION_LLM_OBSERVE_LLM_PARSE_STATUS_LLM_OK_COUNT  signal_decision_llm_observe llm_parse_status_llm_ok_count 下限（默认 -1 忽略）
  WITH_AGENT_SIGNAL_DECISION_LLM_OBSERVE_TREND_RECOMMENDATION_HINT  是否输出 llm_observe trend recommendation 发布提示（1/0，默认 1）
  WITH_AGENT_ACTION_HINT_CASES_REPORT  是否生成 action_hint mismatch 回放 artifact（1/0，默认 1）
  AGENT_ACTION_HINT_CASES_REPORT_PATH  action_hint cases 输出路径（默认 verification/reports/agent_action_hint_cases.latest.json）
  AGENT_ACTION_HINT_MISSING_CASES_REPORT_PATH  action_hint missing cases 输出路径（默认 verification/reports/agent_action_hint_missing_cases.latest.json）
  REQUIRE_AGENT_READYZ_REPORT   是否要求 readyz 报告存在（1/0，默认 1）
  AGENT_READYZ_BASE_URL         agent readyz 地址（默认 http://127.0.0.1:9971）
  AGENT_READYZ_TIMEOUT_S        agent readyz 拉取超时秒数（默认 2.0）

Failure Codes:
  exit 1  任一守卫/测试失败
```
