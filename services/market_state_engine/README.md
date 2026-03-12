# market_state_engine (migration placeholder)

Runtime source path: `market_state_engine/`
Target canonical path: `services/market_state_engine/`

Notes:
- Keep imports/runtime on legacy path during compatibility window.
- `main.py` runtime implementation has moved to `services/market_state_engine/runtime/main.py`.
- Batch A migrated implementations:
  - `services/market_state_engine/src/app.py`
  - `services/market_state_engine/src/routes.py`
  - `services/market_state_engine/src/contracts.py`
- Batch B (phase-1) migrated implementation:
  - `services/market_state_engine/src/service.py`
- Batch B (phase-2) migrated implementation:
  - `services/market_state_engine/src/errors.py`
- Batch B (phase-3) migrated implementation:
  - `services/market_state_engine/src/engine.py`
- Batch B (phase-4) migrated implementation:
  - `services/market_state_engine/src/msl.py`
- Batch B (phase-5) migrated implementation:
  - `services/market_state_engine/src/adapters/in_memory_feature_store.py`
  - `services/market_state_engine/src/adapters/raw_structure_http.py`
