#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'USAGE'
Usage:
  bash tools/local/verify_quick.sh [args...]

Description:
  本地 quick 验证入口，代理到：
    bash tools/ci/verify_quick.sh [args...]
USAGE
  exit 0
fi

bash tools/ci/verify_quick.sh
