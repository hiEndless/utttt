from event_center.indicators_event.engine.plugin_loader import load_plugins
from event_center.indicators_event.engine.indicator_loader import load_all_indicators
from event_center.indicators_event.engine.indicator_view import build_indicator_view
from event_center.indicators_event.scoring.score_mapper import factor_to_score
from event_center.indicators_event.scoring.score_aggregator import aggregate_scores
from event_center.indicators_event.models.event import classify_event
import os
import yaml


def _load_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return {}


def run_event_engine(symbol: str):
    all_indicators = load_all_indicators(symbol)
    plugins = load_plugins()

    base_dir = os.path.dirname(os.path.dirname(__file__))
    cfg_dir = os.path.join(base_dir, "config")
    tf_weights = _load_yaml(os.path.join(cfg_dir, "tf_weights.yaml")) or {}
    strength_weights = _load_yaml(os.path.join(cfg_dir, "strength_weights.yaml")) or {}

    factors = []
    for plugin in plugins:
        view = build_indicator_view(all_indicators, plugin)
        factors.extend(plugin.generate(symbol, view))

    scores = [factor_to_score(f, tf_weights, strength_weights) for f in factors]

    agg = aggregate_scores(scores)
    total = agg["total"]
    direction = agg["direction"]
    level = classify_event(total)
    if agg.get("final_forbidden") and level == "final":
        level = "l1"
    if agg.get("divergence") and level != "raw":
        # optional downgrade by one tier on divergence
        level = "l0" if level == "l1" else ("l1" if level == "final" else level)

    return {
        "symbol": symbol,
        "direction": direction,
        "signal_strength": total,
        "level": level,
        "scores": scores,
        "factors": factors,
        "meta": {
            "tf_sums": agg.get("tf_sums"),
            "bucket_scores": agg.get("bucket_scores"),
            "bucket_dirs": agg.get("bucket_dirs"),
            "divergence": agg.get("divergence"),
            "final_forbidden": agg.get("final_forbidden"),
            "timeframe_alignment": agg.get("timeframe_alignment"),
        }
    }


if __name__ == "__main__":
    res = run_event_engine("BTCUSDT")
    print(res)
