from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from services.execution_service.runtime.main import app, main


if __name__ == "__main__":
    main()
