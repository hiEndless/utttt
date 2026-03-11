#!/usr/bin/env bash
set -euo pipefail

RUN_MODE="${1:-unknown}"
RUNTIME_DOC="event_center_new/docs/runtime.md"

git_sha="unknown"
if command -v git >/dev/null 2>&1; then
  git_sha="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
fi

runtime_config_version="unknown"
if test -f "$RUNTIME_DOC"; then
  runtime_config_version="$(rg -o "runtime_config_version: [a-zA-Z0-9._-]+" "$RUNTIME_DOC" | head -n1 | awk '{print $2}' || echo unknown)"
fi

echo "[CI_META] run_mode=${RUN_MODE}"
echo "[CI_META] git_sha=${git_sha}"
echo "[CI_META] runtime_config_version=${runtime_config_version}"
echo "[CI_META] ts_utc=$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
