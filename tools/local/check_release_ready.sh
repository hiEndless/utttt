#!/usr/bin/env bash
set -euo pipefail

PRINT_SUMMARY_ONLY=0
SUMMARY_FORMAT="text"

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
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
  REQUIRE_AGENT_READYZ_REPORT        quick 是否要求 readyz 报告（默认 0）
  REGRESSION_MAX_AGENT_READYZ_LEVEL  regression 默认 readyz 最大级别（默认 red）
  REGRESSION_REQUIRE_AGENT_READYZ_REPORT regression 默认是否要求 readyz 报告（默认 1）
  NIGHTLY_MAX_AGENT_READYZ_LEVEL     nightly 默认 readyz 最大级别（默认 yellow）
  NIGHTLY_REQUIRE_AGENT_READYZ_REPORT nightly 默认是否要求 readyz 报告（默认 1）
  MAX_LEGACY_CONFIDENCE_RATIO        nightly confidence 占比阈值（默认 0.05）

参数:
  --print-summary-only               仅打印门禁阈值摘要并退出（不执行四步检查）
  --summary-format <text|json>       门禁摘要输出格式（默认 text）
USAGE
      exit 0
      ;;
    --print-summary-only)
      PRINT_SUMMARY_ONLY=1
      shift
      ;;
    --summary-format)
      SUMMARY_FORMAT="${2:-$SUMMARY_FORMAT}"
      shift 2
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      echo "使用 --help 查看可用参数。"
      exit 1
      ;;
  esac
done

if [[ "$SUMMARY_FORMAT" != "text" && "$SUMMARY_FORMAT" != "json" ]]; then
  echo "[失败] --summary-format 仅支持 text 或 json，当前: $SUMMARY_FORMAT"
  exit 1
fi

MAX_LEGACY_CONFIDENCE_RATIO="${MAX_LEGACY_CONFIDENCE_RATIO:-0.05}"
QUICK_WITH_AGENT_READYZ="${WITH_AGENT_READYZ:-0}"
QUICK_MAX_AGENT_READYZ_LEVEL="${MAX_AGENT_READYZ_LEVEL:-red}"
QUICK_REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-0}"
REGRESSION_MAX_AGENT_READYZ_LEVEL="${REGRESSION_MAX_AGENT_READYZ_LEVEL:-red}"
REGRESSION_REQUIRE_AGENT_READYZ_REPORT="${REGRESSION_REQUIRE_AGENT_READYZ_REPORT:-1}"
NIGHTLY_MAX_AGENT_READYZ_LEVEL="${NIGHTLY_MAX_AGENT_READYZ_LEVEL:-yellow}"
NIGHTLY_REQUIRE_AGENT_READYZ_REPORT="${NIGHTLY_REQUIRE_AGENT_READYZ_REPORT:-1}"

if [[ "$SUMMARY_FORMAT" == "json" ]]; then
  cat <<JSON
{
  "schema_version": "release-gate-summary-v1",
  "quick": {
    "with_agent_readyz": ${QUICK_WITH_AGENT_READYZ},
    "max_agent_readyz_level": "${QUICK_MAX_AGENT_READYZ_LEVEL}",
    "require_agent_readyz_report": ${QUICK_REQUIRE_AGENT_READYZ_REPORT}
  },
  "regression_default": {
    "max_agent_readyz_level": "${REGRESSION_MAX_AGENT_READYZ_LEVEL}",
    "require_agent_readyz_report": ${REGRESSION_REQUIRE_AGENT_READYZ_REPORT}
  },
  "nightly_default": {
    "max_agent_readyz_level": "${NIGHTLY_MAX_AGENT_READYZ_LEVEL}",
    "require_agent_readyz_report": ${NIGHTLY_REQUIRE_AGENT_READYZ_REPORT},
    "max_legacy_confidence_ratio": ${MAX_LEGACY_CONFIDENCE_RATIO}
  },
  "checklist_template": "docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md"
}
JSON
else
  echo "[release-gate] readyz/confidence threshold summary"
  echo "[release-gate] quick: WITH_AGENT_READYZ=$QUICK_WITH_AGENT_READYZ MAX_AGENT_READYZ_LEVEL=$QUICK_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$QUICK_REQUIRE_AGENT_READYZ_REPORT"
  echo "[release-gate] regression(default): MAX_AGENT_READYZ_LEVEL=$REGRESSION_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REGRESSION_REQUIRE_AGENT_READYZ_REPORT"
  echo "[release-gate] nightly(default): MAX_AGENT_READYZ_LEVEL=$NIGHTLY_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$NIGHTLY_REQUIRE_AGENT_READYZ_REPORT MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
  echo "[release-gate] checklist template: docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md"
fi

if [[ "$PRINT_SUMMARY_ONLY" == "1" ]]; then
  if [[ "$SUMMARY_FORMAT" == "text" ]]; then
    echo "[通过] summary only 模式完成。"
  fi
  exit 0
fi

echo "[1/4] verify_quick"
bash tools/ci/verify_quick.sh

echo "[2/4] new_arch_guards_full --quick"
bash tools/ci/new_arch_guards_full.sh --quick

echo "[3/4] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[4/4] release baseline alignment --check-origin"
bash tools/local/check_release_baseline_alignment.sh --check-origin

echo "[通过] release ready 检查完成。"
