from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from services.market_state_engine.runtime.main import app, main


if __name__ == "__main__":
    main()
