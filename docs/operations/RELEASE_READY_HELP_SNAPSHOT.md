# Release Ready Help Snapshot

更新时间：2026-03-14

用于冻结 `tools/local/check_release_ready.sh --help` 输出，防止发布门禁参数语义漂移。

## 刷新命令

```bash
bash tools/local/check_release_ready.sh --help
bash tools/local/check_release_ready_help_snapshot_guard.sh
```

## `tools/local/check_release_ready.sh --help`

```text
用法:
  bash tools/local/check_release_ready.sh
  bash tools/local/check_release_ready.sh --print-summary-only [--summary-format text|json]

说明:
  一键执行发布就绪四步检查：
  1) verify_quick
  2) new_arch_guards_full --quick
  3) release triage block guard
  4) release baseline alignment --check-origin

环境变量（可选）:
  WITH_AGENT_READYZ                  quick 观测开关（默认 0）
  MAX_AGENT_READYZ_LEVEL             quick readyz 最大级别（默认 red）
  MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS quick decision_trace schema guard invalid 上限（默认 -1 忽略）
  REQUIRE_AGENT_READYZ_REPORT        quick 是否要求 readyz 报告（默认 0）
  REGRESSION_MAX_AGENT_READYZ_LEVEL  regression 默认 readyz 最大级别（默认 red）
  REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS regression 默认 decision_trace schema guard invalid 上限（默认 -1 忽略）
  REGRESSION_REQUIRE_AGENT_READYZ_REPORT regression 默认是否要求 readyz 报告（默认 1）
  NIGHTLY_MAX_AGENT_READYZ_LEVEL     nightly 默认 readyz 最大级别（默认 yellow）
  NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS nightly 默认 decision_trace schema guard invalid 上限（默认 0）
  NIGHTLY_REQUIRE_AGENT_READYZ_REPORT nightly 默认是否要求 readyz 报告（默认 1）
  MAX_LEGACY_CONFIDENCE_RATIO        nightly confidence 占比阈值（默认 0.05）
  AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH recommendation 报告路径（默认 verification/reports/agent_signal_decision_replay_recommendation.latest.json）

参数:
  --print-summary-only               仅打印门禁阈值摘要并退出（不执行四步检查）
  --summary-format <text|json>       门禁摘要输出格式（默认 text）
```
