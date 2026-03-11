#!/usr/bin/env bash
set -euo pipefail

MODE="full"
for arg in "$@"; do
  case "$arg" in
    --quick)
      MODE="quick"
      ;;
    --event-center-quick)
      MODE="event-center-quick"
      ;;
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/ci/verify_all.sh
  bash tools/ci/verify_all.sh --quick
  bash tools/ci/verify_all.sh --event-center-quick

Modes:
  full                -> scripts/check_new_arch_guards.sh
  quick               -> contract index + state->agent + agent->execution
  event-center-quick  -> scripts/check_new_arch_guards.sh --event-center-quick
USAGE
      exit 0
      ;;
    *)
      echo "[fail] unsupported arg: $arg"
      exit 1
      ;;
  esac
done

if [[ "$MODE" == "event-center-quick" ]]; then
  bash scripts/check_new_arch_guards.sh --event-center-quick
  exit 0
fi

if [[ "$MODE" == "quick" ]]; then
  bash scripts/check_contract_docs_index_guard.sh
  bash scripts/check_contract_docs_index_help_snapshot_guard.sh
  bash scripts/check_state_to_agent_contract_guard.sh
  bash scripts/check_agent_to_execution_guard.sh
  exit 0
fi

bash scripts/check_new_arch_guards.sh
