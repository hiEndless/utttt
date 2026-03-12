#!/usr/bin/env bash
set -euo pipefail

bash tools/local/check_event_center_replay_guard.sh
bash tools/local/check_event_center_replay_summary_schema_guard.sh
