from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

from market_state_engine.contracts import MarketStateMSL
from market_state_engine.state_inference.msl_generator_v1 import build_msl_v1
from market_state_engine.state_inference.msl_generator_v2 import build_msl_v2

if TYPE_CHECKING:
    from market_state_engine.engine import MarketStateFeatures


_DEFAULT_INFERENCE_VERSION = "msl_generator_v1"

_GENERATORS = {
    "msl_generator_v1": build_msl_v1,
    "msl_generator_v2": build_msl_v2,
}


def get_supported_inference_versions() -> List[str]:
    return sorted(list(_GENERATORS.keys()))


def build_msl(
    *,
    features: "MarketStateFeatures",
    state: Dict[str, str],
    plugin_evidence: Dict[str, Dict[str, str]],
    warnings: List[str],
    inference_version: str,
) -> Tuple[MarketStateMSL, str]:
    chosen = str(inference_version or _DEFAULT_INFERENCE_VERSION)
    fn = _GENERATORS.get(chosen) or _GENERATORS[_DEFAULT_INFERENCE_VERSION]
    normalized = chosen if chosen in _GENERATORS else _DEFAULT_INFERENCE_VERSION
    return fn(features=features, state=state, plugin_evidence=plugin_evidence, warnings=warnings), normalized
