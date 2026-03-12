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
