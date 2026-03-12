#!/usr/bin/env bash
set -euo pipefail

TAG_NAME="refactor-guard-baseline-20260312"
LATEST_DOC="docs/operations/RELEASE_LATEST.md"
CHECK_ORIGIN=0

for arg in "$@"; do
  case "$arg" in
    --check-origin)
      CHECK_ORIGIN=1
      ;;
    --help|-h)
      cat <<'USAGE'
用法:
  bash tools/local/check_release_baseline_alignment.sh
  bash tools/local/check_release_baseline_alignment.sh --check-origin

说明:
  - 校验 RELEASE_LATEST 单点文档存在且包含关键字段
  - 校验 baseline tag 指向 commit 与本地 HEAD 一致
  - 可选: 校验 baseline tag 指向 commit 与 origin/master 一致
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

echo "[1/4] 检查 RELEASE_LATEST 文档存在"
if [[ ! -f "${LATEST_DOC}" ]]; then
  echo "[失败] 缺少 ${LATEST_DOC}"
  echo "[hint] 建议先执行：bash tools/local/check_release_ready.sh"
  exit 1
fi

echo "[2/4] 检查 RELEASE_LATEST 关键字段"
for pat in \
  "tag:" \
  "${TAG_NAME}" \
  "git rev-parse --short HEAD" \
  "git rev-parse --short ${TAG_NAME}\\^\\{\\}" \
  "tools/ci/verify_quick.sh" \
  "tools/ci/new_arch_guards_full.sh --quick"
do
  if ! rg -q "${pat}" "${LATEST_DOC}"; then
    echo "[失败] RELEASE_LATEST 缺少关键项: ${pat}"
    echo "[hint] 建议先执行：bash tools/local/check_release_ready.sh"
    exit 1
  fi
done

echo "[3/4] 校验 baseline tag 与 HEAD 对齐"
tag_commit="$(git rev-parse --short "${TAG_NAME}^{}" 2>/dev/null || true)"
if [[ -z "${tag_commit}" ]]; then
  echo "[失败] baseline tag 不存在: ${TAG_NAME}"
  echo "[hint] 建议先执行：bash tools/local/check_release_ready.sh"
  exit 1
fi
head_commit="$(git rev-parse --short HEAD)"
if [[ "${tag_commit}" != "${head_commit}" ]]; then
  echo "[失败] baseline tag 未对齐 HEAD: tag=${tag_commit}, head=${head_commit}"
  echo "[hint] 建议先执行：bash tools/local/check_release_ready.sh"
  exit 1
fi

echo "[4/4] 可选校验 origin/master 对齐"
if [[ "${CHECK_ORIGIN}" -eq 1 ]]; then
  if git rev-parse --short origin/master >/dev/null 2>&1; then
    origin_commit="$(git rev-parse --short origin/master)"
    if [[ "${tag_commit}" != "${origin_commit}" ]]; then
      echo "[失败] baseline tag 未对齐 origin/master: tag=${tag_commit}, origin=${origin_commit}"
      echo "[hint] 建议先执行：bash tools/local/check_release_ready.sh"
      exit 1
    fi
  else
    echo "[提示] 未发现 origin/master，跳过远端对齐检查。"
  fi
else
  echo "[提示] 未启用 --check-origin，跳过远端对齐检查。"
fi

echo "[通过] release baseline 对齐守卫检查完成。"
