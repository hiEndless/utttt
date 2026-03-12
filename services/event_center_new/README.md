# event_center_new (migration summary)

Runtime source path: `event_center_new/`
Target canonical path: `services/event_center_new/`

Notes:
- Runtime entrypoints:
  - `services/event_center_new/runtime/main.py`
  - `services/event_center_new/runtime/replay_main.py`
- Status:
  - legacy wrappers `event_center_new/{main,replay_main}.py` removed
  - runtime layer migrated with no legacy wrappers
