import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.feature_service.src.normalizers.response_normalizer import (
    normalize_degraded_reasons,
    normalize_exchange,
    normalize_features_payload,
    normalize_raw_market_structure,
    normalize_symbol,
)


def test_normalize_exchange_symbol_and_reasons():
    assert normalize_exchange(" Binance ") == "binance"
    assert normalize_symbol(" ethusdt ") == "ETHUSDT"
    assert normalize_degraded_reasons(["x", "x", " y ", "", None]) == ["x", "y"]


def test_normalize_raw_market_structure_defaults():
    out = normalize_raw_market_structure({"symbol": "ethusdt", "candidate_horizons": ["mid_term", "x"]}, symbol="ETHUSDT")
    assert out["symbol"] == "ETHUSDT"
    assert out["candidate_horizons"] == ["mid_term"]
    assert isinstance(out["pre_decision_structure"], dict)
    assert isinstance(out["horizons"], dict)
    assert isinstance(out["orderbook"], dict)
    assert isinstance(out["open_interest"], dict)
    assert isinstance(out["behavioral"], dict)


def test_normalize_features_payload_defaults():
    out = normalize_features_payload({"derived_metrics": {"candidate_horizons": ["short_term", "bad"]}})
    assert isinstance(out["indicators"], dict)
    assert out["derived_metrics"]["candidate_horizons"] == ["short_term"]
    assert isinstance(out["derived_metrics"]["indicator_metrics"], dict)
    assert isinstance(out["structure_snapshot"]["pre_decision_structure"], dict)
