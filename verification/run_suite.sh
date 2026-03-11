#!/usr/bin/env bash
set -euo pipefail

SUITE="new_arch_full"
for arg in "$@"; do
  case "$arg" in
    --suite=*)
      SUITE="${arg#*=}"
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

case "$SUITE" in
  new_arch_full)
    bash verification/guards/new_arch_full.sh
    ;;
  new_arch_event_center_quick)
    bash verification/guards/new_arch_event_center_quick.sh
    ;;
  contract_docs_index)
    bash verification/guards/contract_docs_index.sh
    ;;
  state_to_agent)
    bash verification/guards/state_to_agent.sh
    ;;
  agent_to_execution)
    bash verification/guards/agent_to_execution.sh
    ;;
  event_center_replay)
    bash verification/guards/event_center_replay.sh
    ;;
  quick)
    bash verification/guards/contract_docs_index.sh
    bash verification/guards/state_to_agent.sh
    bash verification/guards/agent_to_execution.sh
    ;;
  *)
    echo "[fail] unknown suite: $SUITE"
    exit 1
    ;;
esac
