from __future__ import annotations

import sys

from services.market_state_engine.src import engine as _runtime

# Legacy module bridge: expose runtime module under old import path.
sys.modules[__name__] = _runtime
