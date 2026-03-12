#!/usr/bin/env bash
set -euo pipefail

OUT_PATH="verification/reports/memory_summary.latest.json"
EXTRA_ARGS=()

while (($# > 0)); do
  case "$1" in
    --help|-h)
      cat <<'USAGE'
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
USAGE
      exit 0
      ;;
    --output)
      OUT_PATH="${2:-$OUT_PATH}"
      shift 2
      ;;
    --*)
      EXTRA_ARGS+=("$1")
      if (($# > 1)) && [[ "${2:-}" != --* ]]; then
        EXTRA_ARGS+=("$2")
        shift 2
      else
        shift
      fi
      ;;
    *)
      if [[ "$OUT_PATH" == "verification/reports/memory_summary.latest.json" ]]; then
        OUT_PATH="$1"
      else
        EXTRA_ARGS+=("$1")
      fi
      shift
      ;;
  esac
done

if test -x ./venv/bin/python; then
  PY_BIN=./venv/bin/python
else
  PY_BIN=python3
fi

CMD=("$PY_BIN" -m services.agent_server_new.memory_summary_runner --output "$OUT_PATH")
if ((${#EXTRA_ARGS[@]} > 0)); then
  CMD+=("${EXTRA_ARGS[@]}")
fi

exec "${CMD[@]}"
