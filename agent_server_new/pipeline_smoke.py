from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from services.agent_server_new.runtime.pipeline_smoke import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
