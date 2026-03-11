from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from typing import Any, Optional, Sequence

from services.agent_server_new.runtime import runner as _runtime

create_trade_event_workflow_from_env = _runtime.create_trade_event_workflow_from_env
TradeEventInput = _runtime.TradeEventInput
_build_parser = _runtime._build_parser
_parse_payload = _runtime._parse_payload
_run_once = _runtime._run_once


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Keep monkeypatch compatibility for legacy tests patching this module.
    _runtime.create_trade_event_workflow_from_env = create_trade_event_workflow_from_env
    return _runtime.main(argv)


__all__ = [
    "create_trade_event_workflow_from_env",
    "TradeEventInput",
    "_build_parser",
    "_parse_payload",
    "_run_once",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
