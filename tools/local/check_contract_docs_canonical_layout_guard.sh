#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[1/4] 检查 docs/contracts 目录与主入口文件存在"
if ! test -d docs/contracts; then
  echo "[失败] 缺少目录: docs/contracts"
  exit 1
fi
if ! test -f docs/CONTRACT_INDEX.md; then
  echo "[失败] 缺少文件: docs/CONTRACT_INDEX.md"
  exit 1
fi

echo "[2/4] 校验 root->contracts 指针文件集合"
POINTER_FILES=(
  "CONTRACTS_CURL_EXAMPLES.md"
  "CONTRACTS_HTTPIE_EXAMPLES.md"
  "CONTRACTS_QUICK_REF.md"
  "SEMANTIC_GLOSSARY.md"
  "SEMANTIC_STABILITY_GUARDRAILS.md"
)
for file in "${POINTER_FILES[@]}"; do
  root_path="docs/$file"
  nested_path="docs/contracts/$file"
  if ! test -f "$root_path"; then
    echo "[失败] 缺少 root 指针文件: $root_path"
    exit 1
  fi
  if ! test -f "$nested_path"; then
    echo "[失败] 缺少 contracts 实体文件: $nested_path"
    exit 1
  fi
  if ! rg -q "^# Moved$" "$root_path"; then
    echo "[失败] root 文件不是 Moved 指针: $root_path"
    exit 1
  fi
  if ! rg -q -F "Canonical path: \`docs/contracts/$file\`" "$root_path"; then
    echo "[失败] root 指针 canonical 目标不正确: $root_path"
    exit 1
  fi
  if rg -q "^# Moved$" "$nested_path"; then
    echo "[失败] contracts 文件不应为 Moved 指针: $nested_path"
    exit 1
  fi
done

echo "[3/4] 校验 CONTRACT_INDEX 单一真源布局"
if rg -q "^# Moved$" docs/CONTRACT_INDEX.md; then
  echo "[失败] docs/CONTRACT_INDEX.md 不应为指针文件"
  exit 1
fi
if ! test -f docs/contracts/CONTRACT_INDEX.md; then
  echo "[失败] 缺少文件: docs/contracts/CONTRACT_INDEX.md"
  exit 1
fi
if ! rg -q "^# Moved$" docs/contracts/CONTRACT_INDEX.md; then
  echo "[失败] docs/contracts/CONTRACT_INDEX.md 必须是指针文件"
  exit 1
fi
if ! rg -q -F "Canonical path: \`docs/CONTRACT_INDEX.md\`" docs/contracts/CONTRACT_INDEX.md; then
  echo "[失败] docs/contracts/CONTRACT_INDEX.md canonical 目标不正确"
  exit 1
fi

echo "[4/4] 检查 contracts 索引页包含 CONTRACT_INDEX 入口"
if ! test -f docs/contracts/index.md; then
  echo "[失败] 缺少文件: docs/contracts/index.md"
  exit 1
fi
if ! rg -q -F "CONTRACT_INDEX.md" docs/contracts/index.md; then
  echo "[失败] docs/contracts/index.md 缺少 CONTRACT_INDEX.md 入口"
  exit 1
fi

echo "[通过] contract docs canonical layout 守卫检查完成。"

