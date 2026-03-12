#!/usr/bin/env bash
set -euo pipefail

echo "[1/3] verify_quick"
bash tools/ci/verify_quick.sh

echo "[2/3] new_arch_guards_full --quick"
bash tools/ci/new_arch_guards_full.sh --quick

echo "[3/3] release baseline alignment --check-origin"
bash tools/local/check_release_baseline_alignment.sh --check-origin

echo "[通过] release ready 检查完成。"

