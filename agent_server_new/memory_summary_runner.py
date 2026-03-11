from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from services.agent_server_new.runtime.memory_summary_runner import *  # noqa: F401,F403


if __name__ == "__main__":
    raise SystemExit(main())
