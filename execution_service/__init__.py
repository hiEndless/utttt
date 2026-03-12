"""execution_service compatibility package."""

from __future__ import annotations

from pathlib import Path
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)  # type: ignore[name-defined]
_services_pkg = (Path(__file__).resolve().parents[1] / "services" / "execution_service").resolve()
if _services_pkg.is_dir():
    _services_path = str(_services_pkg)
    if _services_path not in __path__:
        __path__.append(_services_path)
