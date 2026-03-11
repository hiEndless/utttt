from __future__ import annotations

# Legacy entrypoint kept for compatibility during migration window.
from pathlib import Path
from typing import Any

from services.event_center_new.runtime import replay_main as _runtime

run_replay_report = _runtime.run_replay_report
format_report = _runtime.format_report
_build_parser = _runtime._build_parser
_to_summary_report = _runtime._to_summary_report


def main(argv: list[str] | None = None) -> int:
    # Keep monkeypatch compatibility for legacy tests patching this module.
    _runtime.run_replay_report = run_replay_report
    _runtime.format_report = format_report
    return _runtime.main(argv)


__all__ = [
    "Path",
    "Any",
    "run_replay_report",
    "format_report",
    "_build_parser",
    "_to_summary_report",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
