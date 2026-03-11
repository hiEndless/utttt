#!/usr/bin/env bash
set -euo pipefail

python3 -m verification.replay.replay_event_center "$@"
