#!/usr/bin/env bash
set -euo pipefail

SNAPSHOT="docs/operations/CLI_HELP_SNAPSHOT.md"
SCRIPT_A="tools/local/run_agent_memory_summary_report.sh"
SCRIPT_B="tools/local/verify_report_aggregate.sh"
SCRIPT_C="tools/local/aggregate_and_check.sh"
SCRIPT_D="tools/local/verify_full.sh"
SCRIPT_E="tools/local/verify_quick.sh"

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

compare_help_snapshot() {
  local script="$1"
  local heading="$2"
  local expected actual diff_output
  expected="$(extract_text_block "$heading" "$SNAPSHOT")"
  if [[ -z "$expected" ]]; then
    echo "[失败] 快照缺少区块: $heading"
    exit 1
  fi
  actual="$(bash "$script" --help)"
  if [[ -z "$actual" ]]; then
    echo "[失败] $script --help 输出为空"
    exit 1
  fi
  if ! diff_output="$(diff -u <(printf "%s\n" "$expected") <(printf "%s\n" "$actual") || true)"; then
    :
  fi
  if [[ -n "$diff_output" ]]; then
    echo "[失败] $script --help 与快照不一致: $SNAPSHOT"
    echo "--- diff (up to 100 lines) ---"
    printf "%s\n" "$diff_output" | sed -n '1,100p'
    exit 1
  fi
}

echo "[1/6] 检查脚本与快照存在"
for file in "$SNAPSHOT" "$SCRIPT_A" "$SCRIPT_B" "$SCRIPT_C" "$SCRIPT_D" "$SCRIPT_E"; do
  if ! test -f "$file"; then
    echo "[失败] 缺少文件: $file"
    exit 1
  fi
done

echo "[2/6] 比对 run_agent_memory_summary_report help 快照"
compare_help_snapshot "$SCRIPT_A" "## \`tools/local/run_agent_memory_summary_report.sh --help\`"

echo "[3/6] 比对 verify_report_aggregate help 快照"
compare_help_snapshot "$SCRIPT_B" "## \`tools/local/verify_report_aggregate.sh --help\`"

echo "[4/6] 比对 aggregate_and_check help 快照"
compare_help_snapshot "$SCRIPT_C" "## \`tools/local/aggregate_and_check.sh --help\`"

echo "[5/6] 比对 verify_full help 快照"
compare_help_snapshot "$SCRIPT_D" "## \`tools/local/verify_full.sh --help\`"

echo "[6/6] 比对 verify_quick help 快照"
compare_help_snapshot "$SCRIPT_E" "## \`tools/local/verify_quick.sh --help\`"

echo "[通过] CLI help 快照守卫检查完成。"
