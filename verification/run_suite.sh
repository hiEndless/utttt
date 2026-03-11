#!/usr/bin/env bash
set -euo pipefail

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

SUITE="new_arch_full"
REPORT_JSON=""
VERIFY_ENV_NAME="${VERIFY_ENV_NAME:-${ENVIRONMENT:-local}}"
VERIFY_SUITE_TAGS="${VERIFY_SUITE_TAGS:-}"

for arg in "$@"; do
  case "$arg" in
    --suite=*)
      SUITE="${arg#*=}"
      ;;
    --report-json=*)
      REPORT_JSON="${arg#*=}"
      ;;
    --quick)
      SUITE="quick"
      ;;
    --event-center-quick)
      SUITE="new_arch_event_center_quick"
      ;;
    --help|-h)
      cat <<'USAGE'
Usage:
  bash verification/run_suite.sh
  bash verification/run_suite.sh --suite=new_arch_full
  bash verification/run_suite.sh --suite=quick
  bash verification/run_suite.sh --quick
  bash verification/run_suite.sh --event-center-quick
  bash verification/run_suite.sh --suite=quick --report-json=verification/reports/quick.json

Suites:
  new_arch_full
  new_arch_event_center_quick
  contract_docs_index
  state_to_agent
  agent_to_execution
  event_center_replay
  quick
USAGE
      exit 0
      ;;
    *)
      echo "[fail] unsupported arg: $arg"
      exit 1
      ;;
  esac
done

SUITE_START_MS="$(now_ms)"
GUARD_NAMES=()
GUARD_STATUSES=()
GUARD_DURATIONS_MS=()
EXIT_CODE=0

run_guard() {
  local name="$1"
  shift
  local started_ms ended_ms duration_ms
  started_ms="$(now_ms)"
  if "$@"; then
    GUARD_NAMES+=("$name")
    GUARD_STATUSES+=("passed")
    ended_ms="$(now_ms)"
    duration_ms="$((ended_ms - started_ms))"
    GUARD_DURATIONS_MS+=("$duration_ms")
    return 0
  fi

  GUARD_NAMES+=("$name")
  GUARD_STATUSES+=("failed")
  ended_ms="$(now_ms)"
  duration_ms="$((ended_ms - started_ms))"
  GUARD_DURATIONS_MS+=("$duration_ms")
  return 1
}

case "$SUITE" in
  new_arch_full)
    run_guard "new_arch_full" bash verification/guards/new_arch_full.sh || EXIT_CODE=1
    ;;
  new_arch_event_center_quick)
    run_guard "new_arch_event_center_quick" bash verification/guards/new_arch_event_center_quick.sh || EXIT_CODE=1
    ;;
  contract_docs_index)
    run_guard "contract_docs_index" bash verification/guards/contract_docs_index.sh || EXIT_CODE=1
    ;;
  state_to_agent)
    run_guard "state_to_agent" bash verification/guards/state_to_agent.sh || EXIT_CODE=1
    ;;
  agent_to_execution)
    run_guard "agent_to_execution" bash verification/guards/agent_to_execution.sh || EXIT_CODE=1
    ;;
  event_center_replay)
    run_guard "event_center_replay" bash verification/guards/event_center_replay.sh || EXIT_CODE=1
    ;;
  quick)
    run_guard "contract_docs_index" bash verification/guards/contract_docs_index.sh || EXIT_CODE=1
    if [[ "$EXIT_CODE" -eq 0 ]]; then
      run_guard "state_to_agent" bash verification/guards/state_to_agent.sh || EXIT_CODE=1
    fi
    if [[ "$EXIT_CODE" -eq 0 ]]; then
      run_guard "agent_to_execution" bash verification/guards/agent_to_execution.sh || EXIT_CODE=1
    fi
    ;;
  *)
    echo "[fail] unknown suite: $SUITE"
    exit 1
    ;;
esac

SUITE_END_MS="$(now_ms)"
SUITE_DURATION_MS="$((SUITE_END_MS - SUITE_START_MS))"
SUITE_STATUS="passed"
if [[ "$EXIT_CODE" -ne 0 ]]; then
  SUITE_STATUS="failed"
fi

GIT_SHA="unknown"
if command -v git >/dev/null 2>&1; then
  if git rev-parse --short HEAD >/dev/null 2>&1; then
    GIT_SHA="$(git rev-parse --short HEAD)"
  fi
fi

SUITE_TAGS_JSON="[]"
if [[ -n "$VERIFY_SUITE_TAGS" ]]; then
  SUITE_TAGS_JSON="$(python3 - <<'PY'
import json
import os

raw = str(os.getenv("VERIFY_SUITE_TAGS", "") or "")
tags = [x.strip() for x in raw.split(",") if x.strip()]
print(json.dumps(tags, ensure_ascii=False))
PY
)"
fi

if [[ -n "$REPORT_JSON" ]]; then
  mkdir -p "$(dirname "$REPORT_JSON")"
  {
    printf '{\n'
    printf '  "schema_version": "verification-report-v2",\n'
    printf '  "suite": "%s",\n' "$SUITE"
    printf '  "git_sha": "%s",\n' "$GIT_SHA"
    printf '  "env": "%s",\n' "$VERIFY_ENV_NAME"
    printf '  "suite_tags": %s,\n' "$SUITE_TAGS_JSON"
    printf '  "status": "%s",\n' "$SUITE_STATUS"
    printf '  "exit_code": %s,\n' "$EXIT_CODE"
    printf '  "started_at_ms": %s,\n' "$SUITE_START_MS"
    printf '  "finished_at_ms": %s,\n' "$SUITE_END_MS"
    printf '  "duration_ms": %s,\n' "$SUITE_DURATION_MS"
    printf '  "guards": [\n'
    for i in "${!GUARD_NAMES[@]}"; do
      sep=","
      if [[ "$i" -eq "$((${#GUARD_NAMES[@]} - 1))" ]]; then
        sep=""
      fi
      printf '    {"name":"%s","status":"%s","duration_ms":%s}%s\n' \
        "${GUARD_NAMES[$i]}" \
        "${GUARD_STATUSES[$i]}" \
        "${GUARD_DURATIONS_MS[$i]}" \
        "$sep"
    done
    printf '  ]\n'
    printf '}\n'
  } > "$REPORT_JSON"
fi

exit "$EXIT_CODE"
