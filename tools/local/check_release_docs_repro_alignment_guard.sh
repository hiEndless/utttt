#!/usr/bin/env bash
set -euo pipefail

LATEST_DOC="docs/operations/RELEASE_LATEST.md"
SUMMARY_DOC="docs/operations/RELEASE_SUMMARY_20260312.md"
HANDOFF_DOC="docs/operations/RELEASE_HANDOFF_20260312.md"

for doc in "$LATEST_DOC" "$SUMMARY_DOC" "$HANDOFF_DOC"; do
  if [[ ! -f "$doc" ]]; then
    echo "[失败] 缺少文档: $doc"
    exit 1
  fi
done

echo "[1/2] 检查三份发布文档均包含 release gate schema 最小复现标题"
for doc in "$LATEST_DOC" "$SUMMARY_DOC" "$HANDOFF_DOC"; do
  if ! rg -q "release gate schema" "$doc"; then
    echo "[失败] 文档缺少 release gate schema 复现标题: $doc"
    exit 1
  fi
done

echo "[2/2] 检查三份发布文档均包含一致的最小复现命令关键行"
for doc in "$LATEST_DOC" "$SUMMARY_DOC" "$HANDOFF_DOC"; do
  for line in \
    "git checkout -b tmp/release-gate-schema-repro" \
    "echo \"// repro\" >> verification/reports/release_gate_summary_v1.schema.json" \
    "bash tools/local/check_contract_change_bundle_guard.sh"; do
    if ! rg -q -F "$line" "$doc"; then
      echo "[失败] 文档缺少最小复现关键行: $doc"
      echo "  - $line"
      exit 1
    fi
  done
done

echo "[通过] release 文档最小复现片段对齐检查完成。"
