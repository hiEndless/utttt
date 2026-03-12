#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/local/verify_full.sh [args...]

Description:
  本地 full 验证入口，代理到：
    bash tools/ci/new_arch_guards_full.sh [args...]

Examples:
  bash tools/local/verify_full.sh
  bash tools/local/verify_full.sh --event-center-only
USAGE
  exit 0
fi

bash tools/ci/new_arch_guards_full.sh "$@"
