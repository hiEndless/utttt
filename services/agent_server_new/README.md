# agent_server_new (migration summary)

Runtime source path: `agent_server_new/`
Target canonical path: `services/agent_server_new/`

Notes:
- Runtime entrypoints:
  - `services/agent_server_new/runtime/runner.py`
  - `services/agent_server_new/runtime/pipeline_smoke.py`
  - `services/agent_server_new/runtime/memory_summary_runner.py`
- Status:
  - legacy wrappers `agent_server_new/{runner,pipeline_smoke,memory_summary_runner}.py` removed
  - runtime layer migrated with no legacy wrappers
