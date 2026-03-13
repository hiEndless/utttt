#!/usr/bin/env bash
set -euo pipefail

SNAPSHOT="docs/operations/RELEASE_READY_HELP_SNAPSHOT.md"
SCRIPT="tools/local/check_release_ready.sh"
HEADING='## `tools/local/check_release_ready.sh --help`'

extract_text_block() {
  local heading="$1"
  local file="$2"
  awk -v heading="$heading" '
    $0 == heading {in_section=1; next}
    in_section && /^```text$/ {in_block=1; next}
    in_block && /^```$/ {exit}
    in_block {print}
  ' "$file"
}

echo "[1/2] 检查脚本与快照存在"
for file in "$SNAPSHOT" "$SCRIPT"; do
  if ! test -f "$file"; then
    echo "[失败] 缺少文件: $file"
    exit 1
  fi
done

echo "[2/2] 比对 release ready help 快照"
expected="$(extract_text_block "$HEADING" "$SNAPSHOT")"
if [[ -z "$expected" ]]; then
  echo "[失败] 快照缺少区块: $HEADING"
  exit 1
fi
actual="$(bash "$SCRIPT" --help)"
if [[ -z "$actual" ]]; then
  echo "[失败] $SCRIPT --help 输出为空"
  exit 1
fi
if ! diff_output="$(diff -u <(printf "%s\n" "$expected") <(printf "%s\n" "$actual") || true)"; then
  :
fi
if [[ -n "${diff_output:-}" ]]; then
  echo "[失败] $SCRIPT --help 与快照不一致: $SNAPSHOT"
  echo "--- diff (up to 100 lines) ---"
  printf "%s\n" "$diff_output" | sed -n '1,100p'
  exit 1
fi

echo "[通过] release ready help 快照守卫检查完成。"
