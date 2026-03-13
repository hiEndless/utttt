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
QUICK_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:--1}"
QUICK_REQUIRE_AGENT_READYZ_REPORT="${REQUIRE_AGENT_READYZ_REPORT:-0}"
REGRESSION_MAX_AGENT_READYZ_LEVEL="${REGRESSION_MAX_AGENT_READYZ_LEVEL:-red}"
REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:--1}"
REGRESSION_REQUIRE_AGENT_READYZ_REPORT="${REGRESSION_REQUIRE_AGENT_READYZ_REPORT:-1}"
NIGHTLY_MAX_AGENT_READYZ_LEVEL="${NIGHTLY_MAX_AGENT_READYZ_LEVEL:-yellow}"
NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS="${NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS:-0}"
NIGHTLY_REQUIRE_AGENT_READYZ_REPORT="${NIGHTLY_REQUIRE_AGENT_READYZ_REPORT:-1}"
AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH="${AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH:-verification/reports/agent_signal_decision_replay_recommendation.latest.json}"
TS_MS="$(($(date +%s) * 1000))"
ENV_OVERRIDES=()

collect_override() {
  local name="$1"
  if printenv "$name" >/dev/null 2>&1; then
    ENV_OVERRIDES+=("$name")
  fi
}

collect_override "WITH_AGENT_READYZ"
collect_override "MAX_AGENT_READYZ_LEVEL"
collect_override "MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
collect_override "REQUIRE_AGENT_READYZ_REPORT"
collect_override "REGRESSION_MAX_AGENT_READYZ_LEVEL"
collect_override "REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
collect_override "REGRESSION_REQUIRE_AGENT_READYZ_REPORT"
collect_override "NIGHTLY_MAX_AGENT_READYZ_LEVEL"
collect_override "NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS"
collect_override "NIGHTLY_REQUIRE_AGENT_READYZ_REPORT"
collect_override "MAX_LEGACY_CONFIDENCE_RATIO"
collect_override "AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH"

ENV_OVERRIDES_JSON="[]"
if ((${#ENV_OVERRIDES[@]} > 0)); then
  ENV_OVERRIDES_JSON="["
  for i in "${!ENV_OVERRIDES[@]}"; do
    if [[ "$i" != "0" ]]; then
      ENV_OVERRIDES_JSON+=", "
    fi
    ENV_OVERRIDES_JSON+="\"${ENV_OVERRIDES[$i]}\""
  done
  ENV_OVERRIDES_JSON+="]"
fi

RECOMMENDATION_ARTIFACT_JSON="$(RECOMMENDATION_PATH="$AGENT_SIGNAL_DECISION_REPLAY_RECOMMENDATION_REPORT_PATH" python3 - <<'PY'
import json
import os
from pathlib import Path

path = str(os.environ.get("RECOMMENDATION_PATH") or "").strip()
payload = {
    "path": path,
    "status": "missing",
    "schema_version": "",
    "recommend_action": "none",
}

if not path:
    payload["status"] = "missing"
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)

file_path = Path(path)
if not file_path.exists():
    payload["status"] = "missing"
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)

try:
    data = json.loads(file_path.read_text(encoding="utf-8"))
except Exception:
    payload["status"] = "invalid_json"
    print(json.dumps(payload, ensure_ascii=False))
    raise SystemExit(0)

schema_version = str(data.get("schema_version") or "")
status = str(data.get("status") or "").strip()
recommend_action = str(data.get("recommend_action") or "none").strip()
if not recommend_action:
    recommend_action = "none"

payload["schema_version"] = schema_version
payload["recommend_action"] = recommend_action
if schema_version != "agent-signal-decision-replay-trend-recommendation-v1":
    payload["status"] = "unsupported_schema_version"
elif status in {"recommend", "hold", "skip"}:
    payload["status"] = status
else:
    payload["status"] = "unknown_status"

print(json.dumps(payload, ensure_ascii=False))
PY
)"
RECOMMENDATION_RELEASE_HINT="$(RECOMMENDATION_ARTIFACT_JSON="$RECOMMENDATION_ARTIFACT_JSON" python3 - <<'PY'
import json
import os

try:
    payload = json.loads(str(os.environ.get("RECOMMENDATION_ARTIFACT_JSON") or "{}"))
except Exception:
    print("status_unknown 建议人工确认 recommendation artifact")
    raise SystemExit(0)

status = str(payload.get("status") or "").strip()
action = str(payload.get("recommend_action") or "none").strip() or "none"
if status == "recommend":
    print(f"status=recommend 建议评审阈值收紧 action={action}")
elif status == "hold":
    print("status=hold 当前无需调整阈值")
elif status == "skip":
    print("status=skip 当前样本不足，保持观测")
elif status == "missing":
    print("status=missing 未发现 recommendation artifact")
elif status == "invalid_json":
    print("status=invalid_json recommendation artifact 非法")
elif status == "unsupported_schema_version":
    print("status=unsupported_schema_version recommendation artifact 版本不支持")
elif status == "unknown_status":
    print("status=unknown_status recommendation artifact 状态未知")
else:
    print("status_unknown 建议人工确认 recommendation artifact")
PY
)"

if [[ "$SUMMARY_FORMAT" == "json" ]]; then
  cat <<JSON
{
  "schema_version": "release-gate-summary-v1",
  "source": "tools/local/check_release_ready.sh",
  "ts_ms": ${TS_MS},
  "env_overrides": ${ENV_OVERRIDES_JSON},
  "quick": {
    "with_agent_readyz": ${QUICK_WITH_AGENT_READYZ},
    "max_agent_readyz_level": "${QUICK_MAX_AGENT_READYZ_LEVEL}",
    "max_decision_trace_schema_guard_invalid_records": ${QUICK_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS},
    "require_agent_readyz_report": ${QUICK_REQUIRE_AGENT_READYZ_REPORT}
  },
  "regression_default": {
    "max_agent_readyz_level": "${REGRESSION_MAX_AGENT_READYZ_LEVEL}",
    "max_decision_trace_schema_guard_invalid_records": ${REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS},
    "require_agent_readyz_report": ${REGRESSION_REQUIRE_AGENT_READYZ_REPORT}
  },
  "nightly_default": {
    "max_agent_readyz_level": "${NIGHTLY_MAX_AGENT_READYZ_LEVEL}",
    "max_decision_trace_schema_guard_invalid_records": ${NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS},
    "require_agent_readyz_report": ${NIGHTLY_REQUIRE_AGENT_READYZ_REPORT},
    "max_legacy_confidence_ratio": ${MAX_LEGACY_CONFIDENCE_RATIO}
  },
  "recommendation_artifact": ${RECOMMENDATION_ARTIFACT_JSON},
  "checklist_template": "docs/operations/RELEASE_GATE_CHECKLIST_TEMPLATE.md"
}
JSON
else
  echo "[release-gate] readyz/confidence threshold summary"
  echo "[release-gate] quick: WITH_AGENT_READYZ=$QUICK_WITH_AGENT_READYZ MAX_AGENT_READYZ_LEVEL=$QUICK_MAX_AGENT_READYZ_LEVEL MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$QUICK_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS REQUIRE_AGENT_READYZ_REPORT=$QUICK_REQUIRE_AGENT_READYZ_REPORT"
  echo "[release-gate] regression(default): MAX_AGENT_READYZ_LEVEL=$REGRESSION_MAX_AGENT_READYZ_LEVEL MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$REGRESSION_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS REQUIRE_AGENT_READYZ_REPORT=$REGRESSION_REQUIRE_AGENT_READYZ_REPORT"
  echo "[release-gate] nightly(default): MAX_AGENT_READYZ_LEVEL=$NIGHTLY_MAX_AGENT_READYZ_LEVEL MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS=$NIGHTLY_MAX_DECISION_TRACE_SCHEMA_GUARD_INVALID_RECORDS REQUIRE_AGENT_READYZ_REPORT=$NIGHTLY_REQUIRE_AGENT_READYZ_REPORT MAX_LEGACY_CONFIDENCE_RATIO=$MAX_LEGACY_CONFIDENCE_RATIO"
  if ((${#ENV_OVERRIDES[@]} > 0)); then
    echo "[release-gate] env_overrides: ${ENV_OVERRIDES[*]}"
  else
    echo "[release-gate] env_overrides: (none)"
  fi
  echo "[release-gate] recommendation_artifact: ${RECOMMENDATION_ARTIFACT_JSON}"
  echo "[release-gate] recommendation_release_hint: ${RECOMMENDATION_RELEASE_HINT}"
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
