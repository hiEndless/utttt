#!/usr/bin/env bash
set -euo pipefail

TAG_NAME="refactor-guard-baseline-20260312"

while (($# > 0)); do
  case "$1" in
    --tag)
      TAG_NAME="${2:-$TAG_NAME}"
      shift 2
      ;;
    --help|-h)
      cat <<'USAGE'
Usage:
  bash tools/local/finalize_release_baseline.sh [--tag <tag_name>]

Description:
  一键执行发布基线收口动作：
  1) 将 baseline tag 对齐到当前 HEAD
  2) 强制推送该 tag 到远端 origin
  3) 执行 release baseline 对齐校验（含 origin）

Default:
  --tag refactor-guard-baseline-20260312
USAGE
      exit 0
      ;;
    *)
      echo "[失败] 不支持的参数: $1"
      echo "使用 --help 查看用法。"
      exit 1
      ;;
  esac
done

echo "[1/3] baseline tag 对齐 HEAD: ${TAG_NAME}"
git tag -f "${TAG_NAME}"

echo "[2/3] 推送 baseline tag 到 origin"
git push origin -f "refs/tags/${TAG_NAME}"

echo "[3/3] 执行发布基线对齐校验（含 origin）"
bash tools/local/check_release_baseline_alignment.sh --check-origin

echo "[通过] baseline 收口完成。tag=${TAG_NAME}"

