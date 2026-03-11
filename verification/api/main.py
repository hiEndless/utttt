from __future__ import annotations

import os

import uvicorn

from verification.api.app import create_app


def main() -> None:
    host = str(os.getenv("VERIFICATION_API_HOST", "127.0.0.1") or "127.0.0.1").strip()
    port_raw = str(os.getenv("VERIFICATION_API_PORT", "8765") or "8765").strip()
    report_dir = str(os.getenv("VERIFICATION_REPORT_DIR", "verification/reports") or "verification/reports").strip()
    try:
        port = int(port_raw)
    except Exception:
        port = 8765
    app = create_app(report_dir=report_dir)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
