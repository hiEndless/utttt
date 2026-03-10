#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] event_center replay 守卫"
bash scripts/check_event_center_replay_guard.sh

echo "[2/2] event_center selected_event schema 守卫"
bash scripts/check_event_center_selected_schema_guard.sh

echo "[通过] event_center 契约守卫检查完成。"
