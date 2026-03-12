#!/usr/bin/env bash
set -euo pipefail

for arg in "$@"; do
  case "$arg" in
    --help|-h)
      cat <<'USAGE'
用法:
  bash tools/local/check_release_ready.sh

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
USAGE
      exit 0
      ;;
    *)
      echo "[失败] 不支持的参数: $arg"
      echo "使用 --help 查看可用参数。"
      exit 1
      ;;
  esac
done

MAX_LEGACY_CONFIDENCE_RATIO="${MAX_LEGACY_CONFIDENCE_RATIO:-0.05}"
QUICK_WITH_AGENT_READYZ="${WITH_AGENT_READYZ:-0}"
QUICK_MAX_AGENT_READYZ_LEVEL="${MAX_AGENT_READYZ_LEVEL:-red}"
QUICK_REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-0}"
REGRESSION_MAX_AGENT_READYZ_LEVEL="${REGRESSION_MAX_AGENT_READYZ_LEVEL:-red}"
REGRESSION_REQUIRE_AGENT_READYZ_REPORT="${REGRESSION_REQUIRE_AGENT_READYZ_REPORT:-1}"
NIGHTLY_MAX_AGENT_READYZ_LEVEL="${NIGHTLY_MAX_AGENT_READYZ_LEVEL:-yellow}"
NIGHTLY_REQUIRE_AGENT_READYZ_REPORT="${NIGHTLY_REQUIRE_AGENT_READYZ_REPORT:-1}"

echo "[release-gate] readyz/confidence threshold summary"
echo "[release-gate] quick: WITH_AGENT_READYZ=$QUICK_WITH_AGENT_READYZ MAX_AGENT_READYZ_LEVEL=$QUICK_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$QUICK_REQUIRE_AGENT_READYZ_REPORT"
echo "[release-gate] regression(default): MAX_AGENT_READYZ_LEVEL=$REGRESSION_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$REGRESSION_REQUIRE_AGENT_READYZ_REPORT"
echo "[release-gate] nightly(default): MAX_AGENT_READYZ_LEVEL=$NIGHTLY_MAX_AGENT_READYZ_LEVEL REQUIRE_AGENT_READYZ_REPORT=$NIGHTLY_REQUIRE_AGENT_READYZ_REPORT MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
echo "[release-gate] checklist template: docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md"

echo "[1/4] verify_quick"
bash tools/ci/verify_quick.sh

echo "[2/4] new_arch_guards_full --quick"
bash tools/ci/new_arch_guards_full.sh --quick

echo "[3/4] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[4/4] release baseline alignment --check-origin"
bash tools/local/check_release_baseline_alignment.sh --check-origin

echo "[通过] release ready 检查完成。"
