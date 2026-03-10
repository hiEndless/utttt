#!/usr/bin/env bash
set -euo pipefail

echo "[1/8] event_center replay CLI 参数快照"
help_text="$(python3 -m event_center_new.replay_main --help)"
if ! echo "$help_text" | rg -q -- "--strict"; then
  echo "[失败] replay CLI 缺少 --strict 参数"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--ignore-field"; then
  echo "[失败] replay CLI 缺少 --ignore-field 参数"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--output"; then
  echo "[失败] replay CLI 缺少 --output 参数"
  exit 1
fi
if ! echo "$help_text" | rg -q -- "--summary-only"; then
  echo "[失败] replay CLI 缺少 --summary-only 参数"
  exit 1
fi

echo "[2/8] event_center replay 守卫"
bash scripts/check_event_center_replay_guard.sh

echo "[3/8] event_center replay strict CI 守卫"
bash scripts/check_event_center_replay_strict_ci.sh

echo "[4/8] event_center selected_event schema 守卫"
bash scripts/check_event_center_selected_schema_guard.sh

echo "[5/8] event_center replay summary schema 守卫"
bash scripts/check_event_center_replay_summary_schema_guard.sh

echo "[6/8] event_center runtime 守卫"
bash scripts/check_event_center_runtime_guard.sh

echo "[7/8] event_center runtime 文档守卫"
bash scripts/check_event_center_runtime_doc_guard.sh

echo "[8/8] event_center runtime bump tool 守卫"
bash scripts/check_event_center_runtime_bump_tool_guard.sh

echo "[通过] event_center 契约守卫检查完成。"
