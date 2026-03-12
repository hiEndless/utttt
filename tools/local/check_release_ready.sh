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

echo "[1/4] verify_quick"
bash tools/ci/verify_quick.sh

echo "[2/4] new_arch_guards_full --quick"
bash tools/ci/new_arch_guards_full.sh --quick

echo "[3/4] release triage block guard"
bash tools/local/check_release_triage_block_guard.sh

echo "[4/4] release baseline alignment --check-origin"
bash tools/local/check_release_baseline_alignment.sh --check-origin

echo "[通过] release ready 检查完成。"
