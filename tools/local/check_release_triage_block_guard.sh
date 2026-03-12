#!/usr/bin/env bash
set -euo pipefail

LATEST_DOC="docs/operations/RELEASE_LATEST.md"
SUMMARY_DOC="docs/operations/RELEASE_SUMMARY_20260312.md"
HANDOFF_DOC="docs/operations/RELEASE_HANDOFF_20260312.md"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
用法:
  bash tools/local/check_release_triage_block_guard.sh

说明:
  校验 RELEASE_LATEST / RELEASE_SUMMARY_20260312 / RELEASE_HANDOFF_20260312
  三份文档中的“标准排障命令”代码块文本保持一致，防止运行手册漂移。
EOF
  exit 0
fi

for doc in "$LATEST_DOC" "$SUMMARY_DOC" "$HANDOFF_DOC"; do
  if [[ ! -f "$doc" ]]; then
    echo "[失败] 缺少文档: $doc"
    exit 1
  fi
done

extract_standard_triage_block() {
  local file="$1"
  awk '
    BEGIN { in_target=0; in_code=0 }
    /标准排障命令/ { in_target=1; next }
    in_target && /^```bash[[:space:]]*$/ { in_code=1; next }
    in_code && /^```[[:space:]]*$/ { exit }
    in_code { print }
  ' "$file"
}

tmp_latest="$(mktemp)"
tmp_summary="$(mktemp)"
tmp_handoff="$(mktemp)"
trap 'rm -f "$tmp_latest" "$tmp_summary" "$tmp_handoff"' EXIT

extract_standard_triage_block "$LATEST_DOC" > "$tmp_latest"
extract_standard_triage_block "$SUMMARY_DOC" > "$tmp_summary"
extract_standard_triage_block "$HANDOFF_DOC" > "$tmp_handoff"

for pair in "latest:$tmp_latest" "summary:$tmp_summary" "handoff:$tmp_handoff"; do
  name="${pair%%:*}"
  path="${pair#*:}"
  if [[ ! -s "$path" ]]; then
    echo "[失败] 文档未提取到标准排障命令代码块: $name"
    exit 1
  fi
done

echo "[1/2] 校验 RELEASE_LATEST 与 RELEASE_SUMMARY 排障命令块一致"
if ! diff -u "$tmp_latest" "$tmp_summary" >/dev/null; then
  echo "[失败] RELEASE_LATEST 与 RELEASE_SUMMARY 的标准排障命令块不一致"
  diff -u "$tmp_latest" "$tmp_summary" || true
  exit 1
fi

echo "[2/2] 校验 RELEASE_LATEST 与 RELEASE_HANDOFF 排障命令块一致"
if ! diff -u "$tmp_latest" "$tmp_handoff" >/dev/null; then
  echo "[失败] RELEASE_LATEST 与 RELEASE_HANDOFF 的标准排障命令块不一致"
  diff -u "$tmp_latest" "$tmp_handoff" || true
  exit 1
fi

echo "[通过] release triage block 守卫检查完成。"
